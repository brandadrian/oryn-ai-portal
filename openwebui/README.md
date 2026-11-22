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

## Bilder & Memes (ComfyUI, Qwen-Image 2.1)

Workspace-Modell **Bilder & Memes** (`bilder-memes`, Chat-Modell `qwen3.8:27b-q4-256k`): Bildgenerierung ist standardmässig an, das Modell schreibt den Bild-Prompt und ruft `generate_image` auf. Ein angehängtes Bild wird mit `edit_image` bearbeitet (Text ersetzen, Dinge hinzufügen). Text im Bild klappt auch auf Deutsch mit Umlauten.

- Engine: ComfyUI aus Comfy Desktop, ohne Fenster gestartet von `scripts/comfyui.ps1` (Port 8188, nur 127.0.0.1, Open WebUI erreicht es über `host.docker.internal:8188`).
- Modell: Qwen-Image 2.1 Turbo int8 (8 Schritte, `Comfy-Org/Qwen-Image-2.1`): `diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors` (7.3 GB), `text_encoders/qwen3vl_8b_int8_convrot.safetensors` (9.4 GB), `vae/qwen_image_2.1_vae_bf16.safetensors`. Liegt in `%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\models`. Lizenz: Qwen Research License, nur nicht-kommerziell.
- Workflows (API-Format): `comfyui/qwen-image-2.1-turbo-t2i.json` und `comfyui/qwen-image-2.1-turbo-edit.json`. `config.json` → `bilder` verweist darauf, `setup.py` liest sie ein.
- GPU: RX 7800 XT neben dem Scout (11435), ca. 20-30 s pro Bild bei 1024×1024. Nicht auf der R9700: dort belegt qwen3.8 (256k) ca. 28 GB, ComfyUI hat Windows gezwungen, Teile davon in den RAM zu schieben (33 → 7 t/s bis zum Neuladen). ROCm sieht den VRAM von Ollama (Vulkan) nicht, deshalb `--reserve-vram 11` und `--disable-smart-memory`.
- Stolpersteine (im Skript gelöst): Avast setzt `SSLKEYLOGFILE` → Absturz "no OPENSSL_Applink"; hipBLASLt stürzt bei fp32-Batch-Matmul ab → `TORCH_BLAS_PREFER_HIPBLASLT=0` und `ROCBLAS_USE_HIPBLASLT=0`.
- Comfy Desktop (Fenster-App) nicht gleichzeitig mit Qwen-Image nutzen, sie lädt auf die R9700.

Bedienung: `scripts\comfyui.ps1 -Mode start|stop|restart|status`, Autostart beim Anmelden mit `-Mode install`. Log: `%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs\ComfyUI\logs\headless-8188.log`.

## Dokumente

Workspace-Modell **Dokumente** (`dokumente`, Basis `qwen3-vl:32b-instruct`, 32k Kontext, temp 0.1): liest PDFs, Scans, Belege und Screenshots genau aus. Bilder und Screenshots sieht das Modell direkt. PDFs werden von Open WebUI als Text eingelesen, Bilder in PDFs (Scans) per OCR (`PDF_EXTRACT_IMAGES`, `config.json` → `dokumente`). Für schwierige Scans die Seite besser als Bild anhängen.

Läuft auf der R9700 (24.7 GB, 66/66 Layer) und verdrängt dort qwen3.8, das danach wieder geladen wird (ca. 20 s).

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
