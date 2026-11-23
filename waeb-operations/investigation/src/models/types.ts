import type { allowedTools } from "../services/allowed-tools.js";

export type Environment = "prod" | "staging";
export type McpServerName = keyof typeof allowedTools;
export type Endpoints = Partial<Record<McpServerName | "shopware", string>>;

export type Settings = {
  environment: Environment;
  model: string;
  ollamaUrl: string;
  shopwareKey: string;
  maxCalls: number;
};
