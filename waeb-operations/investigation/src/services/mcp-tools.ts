import { createMCPClient, type MCPClient } from "@ai-sdk/mcp";
import { dynamicTool, type ToolSet } from "ai";
import { allowedTools } from "./allowed-tools.js";
import { describeError, type ToolExecution } from "./tool-execution.js";
import type { Endpoints, Environment, McpServerName } from "../models/types.js";

export async function connectMcpServers(
  environment: Environment,
  endpoints: Endpoints | undefined,
  toolExecution: ToolExecution,
  clients: MCPClient[],
  warnings: string[],
): Promise<ToolSet> {
  const availableTools: ToolSet = {};

  for (const serverName of Object.keys(allowedTools) as McpServerName[]) {
    const hostname = serverName === "metrics" ? "waeb-ops-metrics" : `waeb-ops-${serverName}-${environment}`;
    const serverUrl = endpoints?.[serverName] ?? `http://${hostname}:8000/mcp`;

    try {
      const client = await createMCPClient({
        transport: { type: "http", url: serverUrl, terminateSessionOnClose: false },
        protocolVersionDiscovery: false,
        initializationOptions: { timeout: 10000 },
        onUncaughtError: (error) => console.error(`MCP ${serverName}: ${describeError(error)}`),
      });
      clients.push(client);

      let toolPage = await client.listTools({ options: { timeout: 10000 } });
      const toolDefinitions = [...toolPage.tools];
      const visitedPages = new Set<string>();
      while (toolPage.nextCursor) {
        if (visitedPages.has(toolPage.nextCursor) || visitedPages.size >= 20) {
          throw new Error("Ungültige oder zu lange MCP-Tool-Paginierung.");
        }
        visitedPages.add(toolPage.nextCursor);
        toolPage = await client.listTools({
          params: { cursor: toolPage.nextCursor },
          options: { timeout: 10000 },
        });
        toolDefinitions.push(...toolPage.tools);
      }

      const discoveredTools = client.toolsFromDefinitions({ tools: toolDefinitions });
      for (const toolName of allowedTools[serverName]) {
        const definition = discoveredTools[toolName];
        if (!definition) {
          warnings.push(`${serverName}: erwartetes Tool ${toolName} fehlt.`);
          continue;
        }

        const fullToolName = `${serverName}_${toolName}`;
        availableTools[fullToolName] = dynamicTool({
          description: definition.description,
          inputSchema: definition.inputSchema,
          execute: async (input) => toolExecution.execute(fullToolName, input, async () => {
            if (!input || typeof input !== "object" || Array.isArray(input)) {
              throw new Error("Tool-Eingabe muss ein Objekt sein.");
            }
            return client.callTool({
              name: toolName,
              arguments: Object.fromEntries(Object.entries(input)),
              options: { timeout: 90000 },
            });
          }),
        });
      }
    } catch (error) {
      warnings.push(`${serverName} nicht verfügbar: ${describeError(error)}`);
    }
  }

  return availableTools;
}

export async function closeMcpServers(clients: MCPClient[]): Promise<void> {
  const closeResults = await Promise.allSettled(clients.map((client) => client.close()));
  for (const closeResult of closeResults) {
    if (closeResult.status === "rejected") {
      console.error(`MCP-Verbindung konnte nicht geschlossen werden: ${describeError(closeResult.reason)}`);
    }
  }
}
