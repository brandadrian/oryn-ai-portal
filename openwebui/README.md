# Open WebUI

Chat und Modellverwaltung mit Login. Details: [docs/openwebui.md](../docs/openwebui.md)

## Websuche

1. Admin → Einstellungen → Websuche: einschalten und Suchmaschine wählen. DuckDuckGo braucht keinen Key. Für Brave einen Key unter https://api-dashboard.search.brave.com holen (der Gratis-Plan verlangt eine Kreditkarte) und als Brave API Key eintragen. Den Key nie ins Repo schreiben.
2. Admin → Modelle → Modell bearbeiten → Fähigkeiten: Websuche aktivieren.
3. Im Chat über ➕ die Websuche einschalten.

Funktionsaufruf auf "Standard" lassen, damit es auch mit Modellen ohne Tool-Unterstützung funktioniert.

## Standardmodell (Websuche + Gmail)

Neue Chats starten mit **Assistent · Websuche & Gmail** (`assistent`, Basis `qwen3.8:27b-q4-256k`): Websuche (Brave) und Gmail/Kalender-Tools (`gmail-mcp` aus oryn-gateway) sind von Anfang an aktiv, native Tool-Aufrufe. Definiert in `config.json`, eingespielt vom Dienst `setup` (bei jedem `docker compose up`):

```
docker compose run --rm --no-deps setup
```

`config.json` enthält ausserdem die Admin-Konfiguration, damit sie nicht nur in der Datenbank steckt: Ollama-Verbindungen, Websuche (Brave), Tool-Server (Gmail), Task-Modell, Standardmodell, Modell-Reihenfolge, Favoriten und Namen/Beschreibungen der Basismodelle. Änderungen in der Admin-Oberfläche werden beim nächsten Setup überschrieben, also hier eintragen.

`.env` braucht `WEBUI_ADMIN_EMAIL`/`WEBUI_ADMIN_PASSWORD` (oder `WEBUI_ADMIN_TOKEN`) sowie die Geheimnisse `BRAVE_SEARCH_API_KEY`, `GMAIL_MCP_KEY`, `OLLAMA_SCOUT_KEY`.

## Dokumente

Workspace-Modell **Dokumente** (`dokumente`, Basis `qwen3-vl:32b-instruct`, 32k Kontext, temp 0.1): liest PDFs, Scans, Belege und Screenshots genau aus. Bilder und Screenshots sieht das Modell direkt. PDFs werden von Open WebUI als Text eingelesen, Bilder in PDFs (Scans) per OCR (`PDF_EXTRACT_IMAGES`, `config.json` → `dokumente`). Für schwierige Scans die Seite besser als Bild anhängen.

Läuft auf der R9700 (24.7 GB, 66/66 Layer, `use_mmap false`) und verdrängt dort qwen3.8, das danach wieder geladen wird (ca. 20 s).

## Favoriten

In der Seitenleiste angepinnt:

- **Analyse:** `qwen3.8:27b`
- **Schnell:** `gpt-oss:20b`
- **Bilder und Rechnungen:** `qwen3-vl:8b-instruct`

## Modelle

| Modell | Beschreibung |
|--------|--------------|
| `qwen3.8:27b-agent` | Für Agenten und Tool-Calls (z.B. Copilot): stabil, 128k Kontext, läuft komplett auf der GPU. |
| `qwen3.8:27b` | Das klügste Modell: Analysen und Code, läuft komplett auf der GPU. |
| `gpt-oss:20b` | Sehr schnell, für Chat und schwierige Fragen mit längerem Nachdenken, ohne Bilder. |
| `qwen3.5:9b` | Schneller Allrounder mit Denkmodus, versteht auch Bilder. |
| `qwen3-vl:8b-instruct` | Für Bilder und Rechnungen: Inhalte direkt auslesen, ohne Denkmodus. |
| `saba:latest` | Eigener Chat-Bot Saba mit eigenem Sprachstil, locker und witzig. |
| `gemma3:27b` | Basis für Saba. Gutes Deutsch, kreativ, versteht auch Bilder. |
