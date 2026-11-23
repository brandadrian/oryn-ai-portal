import { tool, type ToolSet } from "ai";
import * as zod from "zod";
import type { ToolExecution } from "./tool-execution.js";
import type { Endpoints, Settings } from "../models/types.js";

export function addShopwareSearch(
  availableTools: ToolSet,
  settings: Settings,
  endpoints: Endpoints | undefined,
  toolExecution: ToolExecution,
  warnings: string[],
): void {
  if (!settings.shopwareKey) {
    warnings.push("Shopware nicht verfügbar: MCPO-Key fehlt.");
    return;
  }

  const shopwareUrl = endpoints?.shopware ?? `http://waeb-ops-shopware-${settings.environment}:8000`;
  availableTools.shopware_search = tool({
    description: "Nur lesende Shopware-Suche nach Entity mit DAL-Kriterien, z.B. filter, includes und limit.",
    inputSchema: zod.object({
      entity: zod.string().regex(/^[a-z_]+$/),
      criteria: zod.record(zod.string(), zod.unknown()),
    }),
    execute: async (input) => toolExecution.execute("shopware_search", input, async () => {
      const response = await fetch(`${shopwareUrl}/shopware_search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${settings.shopwareKey}` },
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(90000),
        redirect: "error",
      });
      if (!response.ok) throw new Error(`Shopware HTTP ${response.status}`);
      return response.json();
    }),
  });
}
