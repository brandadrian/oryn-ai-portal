#!/usr/bin/env node
// Read-only MCP server for Loki. Only sends GET requests to the Loki query API.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer } from "node:http";
import { z } from "zod";

const LOKI_URL = (process.env.LOKI_URL ?? "http://localhost:3100").replace(/\/$/, "");
const MAX_LINES = Number(process.env.LOKI_MAX_LINES ?? 500);
// Obergrenze für die Antwort an das Modell (Zeichen). Grosse Tool-Antworten sprengen sonst den Kontext
// (Ollama schneidet dann den Anfang samt Systemprompt ab). Lieber klar kürzen und sagen, wie man eingrenzt.
const MAX_CHARS = Number(process.env.LOKI_MAX_CHARS ?? 30000);
const MAX_LINE_CHARS = Number(process.env.LOKI_MAX_LINE_CHARS ?? 500);
const MAX_POINTS = 48; // Metrik-Abfragen: höchstens so viele Zeitpunkte pro Serie
const MAX_RANGE_HOURS = Number(process.env.LOKI_MAX_RANGE_HOURS ?? 24);
const TIMEOUT_MS = Number(process.env.LOKI_TIMEOUT_MS ?? 15000);
// Optional: nur diese job-Werte erlauben (Trennung PROD/STAGING), z. B. "shopware,varlogs".
const ALLOWED_JOBS = (process.env.LOKI_ALLOWED_JOBS ?? "").split(",").map((s) => s.trim()).filter(Boolean);

// Jeder Stream-Selektor muss einen job-Matcher mit ausschliesslich erlaubten Werten haben.
function checkJobs(query: string): void {
  if (!ALLOWED_JOBS.length) return;
  const selectors = query.match(/\{[^{}]*\}/g) ?? [];
  if (!selectors.length) throw new Error(`Abfrage braucht einen Selektor mit job, erlaubt: ${ALLOWED_JOBS.join(", ")}`);
  for (const sel of selectors) {
    const m = sel.match(/\bjob\s*(=~|=)\s*"([^"]*)"/);
    if (!m) throw new Error(`Jeder Selektor braucht job="…" (erlaubt: ${ALLOWED_JOBS.join(", ")}): ${sel}`);
    const values = m[1] === "=" ? [m[2]] : m[2].split("|");
    const bad = values.filter((v) => !ALLOWED_JOBS.includes(v.trim()));
    if (bad.length) throw new Error(`job ${bad.join(", ")} ist hier nicht erlaubt. Erlaubt: ${ALLOWED_JOBS.join(", ")}`);
    if (/\bjob\s*(!=|!~)/.test(sel)) throw new Error("Negative job-Matcher sind nicht erlaubt.");
  }
}

// Only these read endpoints are allowed. Push and delete endpoints are never called.
async function lokiGet(path: string, params: Record<string, string> = {}): Promise<any> {
  const url = new URL(LOKI_URL + path);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);

  const headers: Record<string, string> = {};
  if (process.env.LOKI_USERNAME) {
    const token = Buffer.from(`${process.env.LOKI_USERNAME}:${process.env.LOKI_PASSWORD ?? ""}`).toString("base64");
    headers.Authorization = `Basic ${token}`;
  }
  if (process.env.LOKI_ORG_ID) headers["X-Scope-OrgID"] = process.env.LOKI_ORG_ID;

  const res = await fetch(url, { method: "GET", headers, signal: AbortSignal.timeout(TIMEOUT_MS) });
  const body = await res.text();
  if (!res.ok) throw new Error(`Loki ${res.status}: ${body.slice(0, 500)}`);
  return JSON.parse(body);
}

const text = (t: string) => ({ content: [{ type: "text" as const, text: t }] });
const toNs = (ms: number) => (BigInt(Math.floor(ms)) * 1_000_000n).toString();

function buildServer(): McpServer {
const server = new McpServer({ name: "loki-readonly", version: "1.0.0" });

server.registerTool(
  "loki_labels",
  {
    description: "List Loki label names, or the values of one label if `label` is given.",
    inputSchema: { label: z.string().optional().describe("Label name, e.g. 'job'. Empty = list all label names.") },
  },
  async ({ label }) => {
    const path = label ? `/loki/api/v1/label/${encodeURIComponent(label)}/values` : "/loki/api/v1/labels";
    const json = await lokiGet(path);
    return text((json.data ?? []).join("\n") || "(none)");
  },
);

server.registerTool(
  "loki_query_range",
  {
    description:
      `Run a LogQL query over a time range (read-only). Max ${MAX_RANGE_HOURS}h range, max ${MAX_LINES} lines. ` +
      `Example: {job="shopware"} |= "error"`,
    inputSchema: {
      query: z.string().describe("LogQL query"),
      sinceMinutes: z.number().int().positive().optional().describe("Look back N minutes from now (default 60). Ignored if start is set."),
      start: z.string().optional().describe("Start time, ISO 8601"),
      end: z.string().optional().describe("End time, ISO 8601 (default now)"),
      limit: z.number().int().positive().optional().describe(`Max lines (default 100, max ${MAX_LINES})`),
      direction: z.enum(["backward", "forward"]).optional().describe("backward = newest first (default)"),
    },
  },
  async ({ query, sinceMinutes, start, end, limit, direction }) => {
    checkJobs(query);
    const endMs = end ? Date.parse(end) : Date.now();
    let startMs = start ? Date.parse(start) : endMs - (sinceMinutes ?? 60) * 60_000;
    if (Number.isNaN(startMs) || Number.isNaN(endMs)) throw new Error("Invalid start or end time");
    startMs = Math.max(startMs, endMs - MAX_RANGE_HOURS * 3_600_000);

    // Metrik-Abfragen (count_over_time, rate …): Schrittweite so wählen, dass höchstens MAX_POINTS Punkte entstehen
    const isMetric = !/^\s*\{[^}]*\}\s*(\|[^\[]*)?$/.test(query) && /\[[0-9]+[smhd]\]/.test(query);
    const params: Record<string, string> = {
      query,
      start: toNs(startMs),
      end: toNs(endMs),
      limit: String(Math.min(limit ?? 100, MAX_LINES)),
      direction: direction ?? "backward",
    };
    if (isMetric) params.step = `${Math.max(60, Math.ceil((endMs - startMs) / 1000 / MAX_POINTS))}s`;
    const json = await lokiGet("/loki/api/v1/query_range", params);

    const { resultType, result } = json.data ?? {};
    const out: string[] = [];
    let used = 0, shown = 0, total = 0;
    const push = (l: string) => { if (used + l.length + 1 > MAX_CHARS) return false; out.push(l); used += l.length + 1; return true; };
    const fmtTs = (ns: string) => new Date(Number(BigInt(ns) / 1_000_000n)).toISOString().replace(/\.\d+Z$/, "Z");

    if (resultType === "streams") {
      // Labels nur einmal pro Datei/Stream, nicht in jeder Zeile
      for (const s of result) total += s.values.length;
      outer: for (const s of result) {
        const labels = Object.entries(s.stream).filter(([k]) => !["service_name", "detected_level"].includes(k))
          .map(([k, v]) => `${k}="${v}"`).join(", ");
        if (!push(`--- {${labels}}`)) break;
        for (const [ts, line] of s.values) {
          const l = String(line);
          if (!push(`${fmtTs(ts)} ${l.length > MAX_LINE_CHARS ? l.slice(0, MAX_LINE_CHARS) + " …" : l}`)) break outer;
          shown++;
        }
      }
      if (!total) return text("(keine Log-Zeilen)");
      const note = shown < total
        ? `\n[${shown} von ${total} Zeilen gezeigt – Antwort auf ${MAX_CHARS} Zeichen begrenzt. Für mehr: Zeitraum verkürzen, nach Kanal/Datei/Text filtern oder zuerst mit count_over_time zählen.]`
        : `\n[${total} Zeilen]`;
      return text(out.join("\n") + note);
    }

    // Metrik-Abfragen: pro Serie Summe, Maximum, letzter Wert und die Punkte ungleich 0 (kompakt)
    const series = (result ?? []) as Array<{ metric: Record<string, string>; values?: [number, string][]; value?: [number, string] }>;
    if (!series.length) return text("(keine Daten)");
    const rows = series.map((r) => {
      const vals = (r.values ?? (r.value ? [r.value] : [])).map(([t, v]) => [t, Number(v)] as [number, number]);
      const sum = vals.reduce((a, [, v]) => a + v, 0);
      return { r, vals, sum, max: Math.max(...vals.map(([, v]) => v)) };
    }).sort((a, b) => b.max - a.max);
    push(`${rows.length} Serien, ein Wert pro ${params.step ?? "Schritt"}, sortiert nach Höchstwert (Werte = Ergebnis der Abfrage zu diesem Zeitpunkt):`);
    let shownSeries = 0;
    for (const { r, vals, max } of rows) {
      const labels = Object.entries(r.metric).filter(([k]) => !["service_name", "detected_level"].includes(k))
        .map(([k, v]) => `${k}="${v}"`).join(", ");
      const pts = vals.filter(([, v]) => v !== 0).map(([t, v]) => `${new Date(t * 1000).toISOString().slice(11, 16)}=${+v.toFixed(3)}`).join(" ");
      if (!push(`{${labels}} max=${+max.toFixed(3)} zuletzt=${+(vals.at(-1)?.[1] ?? 0).toFixed(3)}${pts ? " | " + pts : ""}`)) break;
      shownSeries++;
    }
    if (shownSeries < rows.length) out.push(`[${shownSeries} von ${rows.length} Serien gezeigt – Antwort begrenzt. Mit sum by (…) oder topk(…) zusammenfassen.]`);
    return text(out.join("\n"));
  },
);

return server;
}

// MCP_HTTP_PORT set: Streamable HTTP on /mcp (stateless, for Open WebUI). Otherwise: stdio (Claude Desktop).
const httpPort = process.env.MCP_HTTP_PORT;
if (httpPort) {
  createServer(async (req, res) => {
    if (req.url !== "/mcp" || req.method !== "POST") {
      res.writeHead(req.url === "/mcp" ? 405 : 404).end();
      return;
    }
    const server = buildServer();
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    res.on("close", () => { transport.close(); server.close(); });
    await server.connect(transport);
    await transport.handleRequest(req, res);
  }).listen(Number(httpPort), "0.0.0.0", () => console.error(`loki-mcp listening on :${httpPort}/mcp`));
} else {
  await buildServer().connect(new StdioServerTransport());
}
