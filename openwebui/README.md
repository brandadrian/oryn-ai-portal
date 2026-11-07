# Open WebUI

Chat und Modellverwaltung mit Login. Details: [docs/openwebui.md](../docs/openwebui.md)

## Websuche

1. Admin → Einstellungen → Websuche: einschalten und Suchmaschine wählen. DuckDuckGo braucht keinen Key. Für Brave einen Key unter https://api-dashboard.search.brave.com holen (der Gratis-Plan verlangt eine Kreditkarte) und als Brave API Key eintragen. Den Key nie ins Repo schreiben.
2. Admin → Modelle → Modell bearbeiten → Fähigkeiten: Websuche aktivieren.
3. Im Chat über ➕ die Websuche einschalten.

Funktionsaufruf auf "Standard" lassen, damit es auch mit Modellen ohne Tool-Unterstützung funktioniert.

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
