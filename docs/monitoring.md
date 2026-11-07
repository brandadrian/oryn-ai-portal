# Monitoring

[← zurück zur README](../README.md)

Zwei Datenquellen, ein Grafana:

| Quelle | Liefert | Ziel |
|--------|---------|------|
| `ollama-monitor/` OllamaMonitor (Windows-Dienst, Solution `ollama-monitor/ollama-monitor.slnx`) | CPU, RAM, GPU-Last, VRAM, Hardware-Infos, geladene Modelle, Tokens aus `server.log` (alle Clients) | Prometheus (OTLP), Loki |
| `api/` meter | pro API-Anfrage: Client, Modell, Tokens, Cache, Zeiten, Status | Loki (`job="ollama-api"`) |

Grafana: https://monitoring.oryn.brandadrian.com/monitor (öffentlich, nur lesen), lokal http://localhost:3000/monitor (Admin).

## Dashboards

Dateien in `monitoring/grafana/dashboards/`, werden beim Start eingelesen (Ordner "Ollama"). Neue Datei → Grafana neu starten.

- **Ollama & Rechner** (`ollama.json`): Hardware (CPU-Modell, RAM, Grafikkarten), Auslastung, VRAM, geladene Modelle, Tokens pro Minute, Geschwindigkeit, Probleme (gekürzte Prompts, Verdrängungen, Ladefehler).
- **Ollama API (Anfragen)** (`ollama-api.json`): Überblick (Anfragen, Tokens, Cache-Treffer, Ø Dauer, Fehler), Tokens pro Client und Modell, Optimierung (Prompt-Grösse vs. Cache, Zeitanteile Warten/Prompt/Ausgabe, Tokens/s), Tabelle der letzten Anfragen. Filter: Client, Modell. Bedeutung der Werte: [api.md](api.md#anfragen-auswerten).

## Stack starten

```bash
cd monitoring && docker compose up -d
```

Prometheus `:9090` (OTLP-Empfang, 365 Tage), Loki `:3100`, Grafana `:3000`. Daten in `monitoring/data/` (nicht im Git, sichern).

## Öffentliches Grafana

Besucher sehen alle Dashboards anonym als Viewer. Traefik sperrt auf den öffentlichen Adressen `/monitor/login`, `/monitor/admin`,
`/monitor/user`, `/monitor/signup`, `/monitor/logout` (404) und entfernt `Authorization`- und `Cookie`-Header.
Damit kann sich öffentlich niemand anmelden, auch nicht mit Admin-Zugang. Admin-Login nur lokal über http://localhost:3000/monitor.

Grafana läuft unter dem Unterpfad `/monitor` (`GF_SERVER_SERVE_FROM_SUB_PATH`), damit `/v1` und `/api` auf derselben Domain der LLM-API gehören.
Die alte Adresse `ollama-monitoring.homelab.brandadrian.com` leitet auf `/monitor/...` weiter.

## OllamaMonitor als Windows-Dienst

Nur nativ unter Windows liefert der Monitor alle Werte (CPU, RAM, GPU-Last, VRAM, Tokens).

1. Release-Build (normale PowerShell, im Ordner `ollama-monitor/`):

   ```powershell
   dotnet publish src/OllamaMonitor/OllamaMonitor.csproj -c Release -r win-x64 --self-contained false -o C:\Services\OllamaMonitor
   ```

2. In `C:\Services\OllamaMonitor\appsettings.json` setzen:
   - `"UseOtel": true`
   - `Monitor:LogPath` auf den vollen Pfad, z.B. `C:\Users\Adrian\AppData\Local\Ollama\server.log`
     (der Dienst läuft als LocalSystem und findet `%LOCALAPPDATA%` des Benutzers sonst nicht)

3. Dienst anlegen und starten (PowerShell **als Administrator**):

   ```powershell
   sc.exe create OllamaMonitor binPath= "C:\Services\OllamaMonitor\OllamaMonitor.exe" start= delayed-auto DisplayName= "Ollama Monitor"
   ```

   ```powershell
   sc.exe start OllamaMonitor
   ```

Aktualisieren: `sc.exe stop OllamaMonitor`, Schritt 1 wiederholen (appsettings.json danach prüfen), `sc.exe start OllamaMonitor`.
Entfernen: `sc.exe stop OllamaMonitor`, dann `sc.exe delete OllamaMonitor`.

Konfiguration (`appsettings.json`): `Monitor:OllamaUrl`, `Monitor:LogPath`, `LocalPrometheus:OtlpEndpoint`, `Loki:Url`,
optional `GrafanaCloud:OtlpEndpoint`/`InstanceId`/`Token` (Token als User-Secret, nicht ins JSON).

Tokens kommen aus den llama.cpp-Zeilen in `server.log` (`prompt eval time … / N tokens`, `eval time …`). Ollama 0.40 hat keinen
`/metrics`-Endpunkt. Der Modellname steht nicht im Log, es zählt das laut `/api/ps` geladene Modell. Der Monitor liest nur neue Zeilen
(Position merken, Start am Dateiende) und öffnet die Datei neu, wenn Ollama sie beim Neustart rotiert.

Alternative ohne Hardware-Werte: Container `docker compose --profile container-monitor up -d` in `monitoring/`.
Nicht beides gleichzeitig laufen lassen, sonst wird doppelt gezählt.
