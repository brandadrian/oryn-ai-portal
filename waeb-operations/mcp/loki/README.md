# Loki MCP (read-only)

Small MCP server that lets Claude Desktop or Open WebUI read logs from Loki. It only sends GET requests to the Loki query API. Push and delete endpoints are never called.

## Tools

| Tool | Loki endpoint | Description |
|---|---|---|
| `loki_labels` | `GET /loki/api/v1/labels`, `GET /loki/api/v1/label/{name}/values` | Label names, or the values of one label. |
| `loki_query_range` | `GET /loki/api/v1/query_range` | LogQL query over a time range (`sinceMinutes` or `start`/`end`). |

Limits: max `LOKI_MAX_RANGE_HOURS` (default 24) per query, max `LOKI_MAX_LINES` (default 500) lines, timeout `LOKI_TIMEOUT_MS` (default 15000).

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LOKI_URL` | `http://localhost:3100` | Loki base URL, without `/loki/api/...`. |
| `LOKI_USERNAME` / `LOKI_PASSWORD` | – | Optional Basic Auth. |
| `LOKI_ORG_ID` | – | Optional `X-Scope-OrgID` header (multi-tenant Loki). |
| `MCP_HTTP_PORT` | – | Set: Streamable HTTP on `/mcp`. Not set: stdio. |

Secrets only go into the Claude Desktop config or a local `.env` (in `.gitignore`), never into the repo.

## 1. SSH tunnel to Loki on Maxcluster

```bash
ssh -N -L 3100:127.0.0.1:3100 <user>@<maxcluster-host>
curl -s http://localhost:3100/ready   # "ready"
```

3100 is the Loki default port. Check host and port on the server.

## 2a. Docker Compose with Open WebUI

```bash
docker compose up -d --build
```

- Open WebUI: http://localhost:3000 (create the admin user on first start).
- Add the MCP server (Open WebUI v0.6.31+): **Admin Settings → Integrations → External Tool Servers → + Add Connection**, type **MCP (Streamable HTTP)**, URL `http://loki-mcp:8000/mcp`, auth **None**, then save.
- The MCP container reaches the tunnel on the host via `host.docker.internal:3100`.
- Open WebUI needs a model connection (OpenAI-compatible API or Ollama), configured in Open WebUI itself.

Source: [Open WebUI MCP docs](https://docs.openwebui.com/features/extensibility/mcp).

## 2b. Claude Desktop (stdio)

```bash
npm ci && npm run build
```

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "loki": {
      "command": "node",
      "args": ["/Users/adrianbrand/source/loki-mcp/dist/index.js"],
      "env": { "LOKI_URL": "http://localhost:3100" }
    }
  }
}
```

Restart Claude Desktop.

## Local test without Maxcluster

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build loki loki-mcp
NOW=$(date +%s)000000000
curl -s -H "Content-Type: application/json" -X POST localhost:3100/loki/api/v1/push \
  --data "{\"streams\":[{\"stream\":{\"job\":\"shopware\"},\"values\":[[\"$NOW\",\"ERROR test\"]]}]}"
curl -s -X POST localhost:8001/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"loki_query_range","arguments":{"query":"{job=\"shopware\"}"}}}'
```
