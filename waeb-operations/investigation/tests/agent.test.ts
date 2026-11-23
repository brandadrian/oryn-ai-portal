import assert from "node:assert/strict";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { once } from "node:events";
import { test } from "node:test";
import { investigate } from "../src/services/investigation.js";
import { reportSchema, validateEvidence } from "../src/models/report.js";

test("Belegreferenzen werden geprüft", () => {
  const report = reportSchema.parse({
    zusammenfassung: "Test",
    root_cause: { aussage: "Hypothese", sicherheit: "mittel", begruendung: "Test" },
    belege: [{ id: "E2", befund: "Test" }],
    fix_vorschlaege: [],
    offene_fragen: [],
  });
  assert.throws(() => validateEvidence(report, new Set(["E1"])), /unbekannten/);
  report.belege = [];
  assert.throws(() => validateEvidence(report, new Set()), /ohne Belege/);
});

test("Agent entdeckt nur freigegebene Tools und begrenzt mehrere Tool-Aufrufe", async () => {
  let modelCalls = 0;
  let toolCalls = 0;
  let mcpFailure = false;
  let offeredTools: string[] = [];
  const server = createServer(async (request: IncomingMessage, response: ServerResponse) => {
    try {
      if (request.method === "GET" && request.url === "/mcp") {
        response.writeHead(405).end();
        return;
      }
      const chunks: Buffer[] = [];
      for await (const chunk of request) chunks.push(Buffer.from(chunk));
      const body: unknown = JSON.parse(Buffer.concat(chunks).toString() || "{}");
      if (!body || typeof body !== "object") throw new Error("Ungültige Testanfrage");
      const data = Object.fromEntries(Object.entries(body));
      response.setHeader("Content-Type", "application/json");
      if (request.url === "/mcp") {
        let result: unknown;
        if (data.method === "initialize") {
          result = { protocolVersion: "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: "test", version: "1" } };
        } else if (data.method === "notifications/initialized") {
          response.writeHead(202).end();
          return;
        } else if (data.method === "tools/list") {
          result = { tools: [
            { name: "datei_lesen", description: "Datei lesen", inputSchema: { type: "object", properties: { pfad: { type: "string" } }, required: ["pfad"] } },
            { name: "datei_loeschen", description: "Nicht erlaubt", inputSchema: { type: "object", properties: {} } },
          ] };
        } else if (data.method === "tools/call") {
          toolCalls++;
          result = mcpFailure
            ? { isError: true, content: [{ type: "text", text: "Datei nicht erreichbar" }] }
            : { content: [{ type: "text", text: "Zeile 42: Testfehler" }] };
        } else {
          throw new Error(`Unerwartete MCP-Methode: ${String(data.method)}`);
        }
        response.end(JSON.stringify({ jsonrpc: "2.0", id: data.id, result }));
        return;
      }
      if (request.url === "/v1/chat/completions") {
        modelCalls++;
        const offered = Array.isArray(data.tools) ? data.tools : [];
        if (modelCalls === 1) {
          offeredTools = offered.map((item: { function: { name: string } }) => item.function.name);
        }
        const report = {
          zusammenfassung: "Testfehler gefunden",
          root_cause: { aussage: "Fehler in Datei", sicherheit: "mittel", begruendung: "Datei enthält Testfehler" },
          belege: [{ id: "E1", befund: "Datei enthält Testfehler in Zeile 42" }],
          fix_vorschlaege: ["Fehler in Datei untersuchen"],
          offene_fragen: [],
        };
        const message = modelCalls === 1
          ? {
              role: "assistant", content: null, tool_calls: [1, 2].map((callNumber) => ({
                id: `call_${callNumber}`, type: "function",
                function: { name: "files_datei_lesen", arguments: JSON.stringify({ pfad: "test.php" }) },
              })),
            }
          : { role: "assistant", content: JSON.stringify(report) };
        response.end(JSON.stringify({
          id: `response_${modelCalls}`, object: "chat.completion", created: 1, model: "test",
          choices: [{ index: 0, message, finish_reason: modelCalls === 1 ? "tool_calls" : "stop" }],
          usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
        }));
        return;
      }
      response.writeHead(404).end();
    } catch (error) {
      response.writeHead(500).end(String(error));
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  const base = `http://127.0.0.1:${address.port}`;
  try {
    const result = await investigate("Testincident", {
      environment: "prod", model: "test", ollamaUrl: `${base}/v1`, shopwareKey: "", maxCalls: 1,
    }, { loki: `${base}/mcp`, files: `${base}/mcp`, mysql: `${base}/mcp`, metrics: `${base}/mcp` });
    assert.ok(offeredTools.includes("files_datei_lesen"));
    assert.ok(!offeredTools.some((name) => name.includes("loeschen")));
    assert.equal(result.umgebung, "prod");
    assert.equal(toolCalls, 1);
    assert.equal(result.tool_aufrufe, 1);
    assert.equal(result.untersuchung[0].id, "E1");
    assert.equal(result.report.belege[0].id, "E1");
    assert.ok(result.warnungen.some((warning) => warning.includes("Tool-Limit")));
    modelCalls = 0;
    const stagingResult = await investigate("Testincident", {
      environment: "staging", model: "test", ollamaUrl: `${base}/v1`, shopwareKey: "", maxCalls: 1,
    }, { loki: `${base}/mcp`, files: `${base}/mcp`, mysql: `${base}/mcp`, metrics: `${base}/mcp` });
    assert.equal(stagingResult.umgebung, "staging");
    modelCalls = 0;
    mcpFailure = true;
    await assert.rejects(() => investigate("Testincident", {
      environment: "staging", model: "test", ollamaUrl: `${base}/v1`, shopwareKey: "", maxCalls: 1,
    }, { loki: `${base}/mcp`, files: `${base}/mcp`, mysql: `${base}/mcp`, metrics: `${base}/mcp` }), /fehlgeschlagenen Beleg/);
  } finally {
    server.close();
    await once(server, "close");
  }
});
