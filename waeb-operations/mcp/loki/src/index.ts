#!/usr/bin/env node
// Read-only MCP server for Loki. Only sends GET requests to the Loki query API.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer } from "node:http";
import { z } from "zod";

const LOKI_URL = (process.env.LOKI_URL ?? "http://localhost:3100").replace(/\/$/, "");
const MAX_LINES = Number(process.env.LOKI_MAX_LINES ?? 500);
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

    const json = await lokiGet("/loki/api/v1/query_range", {
      query,
      start: toNs(startMs),
      end: toNs(endMs),
      limit: String(Math.min(limit ?? 100, MAX_LINES)),
      direction: direction ?? "backward",
    });

    const { resultType, result } = json.data ?? {};
    if (resultType === "streams") {
      const lines: string[] = [];
      for (const s of result) {
        const labels = Object.entries(s.stream).map(([k, v]) => `${k}="${v}"`).join(",");
        for (const [ts, line] of s.values) {
          lines.push(`${new Date(Number(BigInt(ts) / 1_000_000n)).toISOString()} {${labels}} ${line}`);
        }
      }
      return text(lines.join("\n") || "(no log lines)");
    }
    // Metric queries (e.g. count_over_time) return matrix data.
    return text(JSON.stringify(result, null, 2));
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
