export const allowedTools = {
  loki: ["loki_labels", "loki_query_range"],
  files: ["ordner_auflisten", "dateien_suchen", "datei_lesen", "inhalt_suchen"],
  mysql: ["umgebungen", "tabellen_auflisten", "tabelle_beschreiben", "sql_abfrage"],
  metrics: ["server_zustand", "metriken_auflisten", "promql_abfrage", "promql_verlauf"],
} as const;
