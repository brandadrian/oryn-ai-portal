type ToolCallRecord = {
  id: string;
  tool: string;
  eingabe: string;
  status: "ok" | "fehler";
  fehler?: string;
};

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function formatToolData(value: unknown): string {
  const text = JSON.stringify(value);
  if (text === undefined) return "Keine Daten";
  if (text.length > 8000) return `${text.slice(0, 8000)}\n[Ergebnis gekürzt; Abfrage eingrenzen]`;
  return text;
}

export class ToolExecution {
  private callsMade = 0;
  readonly records: ToolCallRecord[] = [];

  constructor(readonly maxCalls: number) {}

  get usedCalls(): number {
    return this.callsMade;
  }

  async execute(toolName: string, input: unknown, operation: () => Promise<unknown>) {
    if (this.callsMade >= this.maxCalls) {
      return { error: `Tool-Limit von ${this.maxCalls} erreicht; keine weitere Abfrage ausgeführt.` };
    }
    this.callsMade++;

    const evidenceId = `E${this.callsMade}`;
    console.error(`[${evidenceId}] ${toolName}`);
    const record: ToolCallRecord = {
      id: evidenceId,
      tool: toolName,
      eingabe: formatToolData(input),
      status: "ok",
    };

    try {
      const result = await operation();
      const hasToolError = typeof result === "object" && result !== null
        && (("isError" in result && result.isError === true) || ("error" in result && Boolean(result.error)));
      if (hasToolError) {
        record.status = "fehler";
        record.fehler = formatToolData(result);
        this.records.push(record);
        return { id: evidenceId, error: record.fehler };
      }

      this.records.push(record);
      return { id: evidenceId, data: formatToolData(result) };
    } catch (error) {
      record.status = "fehler";
      record.fehler = describeError(error);
      this.records.push(record);
      return { id: evidenceId, error: record.fehler };
    }
  }
}
