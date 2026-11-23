# Incident Investigation Agent

Der Agent untersucht Fehler mit Ollama und wählt selbst lesende Tools für Logs, Dateien,
MySQL, Metriken und Shopware. Er gibt einen JSON-Report mit Belegen und Fix-Vorschlägen aus.

## Start

Voraussetzung: Die MCP-Container der gewählten Umgebung und ein vom Container erreichbares
Ollama laufen. Das Modell muss Tool-Calling und strukturierte JSON-Ausgabe unterstützen.

Im Ordner `waeb-operations`:

```powershell
# Einmalig und nach Codeänderungen:
docker compose build investigation-staging

# Untersuchung starten:
docker compose run --rm --no-deps investigation-staging "Checkout liefert seit 14:00 Uhr HTTP 500, Europe/Zurich"
```

Für PROD `investigation-prod` statt `investigation-staging` verwenden. Der Report erscheint
im Terminal; mit `| Out-File -Encoding utf8 report.json` kannst du ihn speichern.

## Einstellungen

Optional in `waeb-operations/.env`:

| Variable | Standard |
|---|---|
| `INVESTIGATION_MODEL` | `qwen3.8:27b-q4-128k` |
| `INVESTIGATION_OLLAMA_URL` | `http://host.docker.internal:11434/v1` |
| `INVESTIGATION_MAX_CALLS` | `100` (erlaubt: 1–100) |

## Wichtig

- PROD-Abfragen lesen echte Daten. Der Agent führt keine Änderungen aus; MySQL benötigt einen Read-only-User.
- Tool-Ergebnisse gehen an das konfigurierte Modell. Nur vertrauenswürdige Endpunkte verwenden.
- Reports können sensible Daten enthalten. Aussagen und Belege vor Entscheidungen prüfen.
- Git- und Bitbucket-Historie sind nicht angebunden.
