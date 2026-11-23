import { investigate } from "./services/investigation.js";
import type { Settings } from "./models/types.js";

async function main() {
  const incident = process.argv.slice(2).join(" ").trim();
  if (!incident) throw new Error("Incident als Argument angeben, z. B. \"Checkout liefert seit 14:00 Uhr HTTP 500\".");
  if (incident.length > 10000) throw new Error("Incident ist zu lang (maximal 10000 Zeichen).");
  const environment = process.env.INVESTIGATION_ENV;
  if (environment !== "prod" && environment !== "staging") {
    throw new Error("INVESTIGATION_ENV muss prod oder staging sein.");
  }
  const maxCalls = Number(process.env.INVESTIGATION_MAX_CALLS || "100");
  if (!Number.isInteger(maxCalls) || maxCalls < 1 || maxCalls > 100) {
    throw new Error("INVESTIGATION_MAX_CALLS muss eine ganze Zahl zwischen 1 und 100 sein.");
  }
  const settings: Settings = {
    environment,
    model: process.env.INVESTIGATION_MODEL || "qwen3.8:27b-q4-128k",
    ollamaUrl: process.env.INVESTIGATION_OLLAMA_URL || "http://host.docker.internal:11434/v1",
    shopwareKey: process.env.INVESTIGATION_SHOPWARE_KEY || "",
    maxCalls,
  };
  const result = await investigate(incident, settings);
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error: unknown) => {
  console.error(`Investigation fehlgeschlagen: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
