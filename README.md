# Oryn AI Portal

Eigene LLMs von aussen nutzen: **API mit Key**, **eigene Modelle**, **Chat (Open WebUI)** und **Monitoring** an einem Ort.
Läuft auf einem Windows-PC mit Ollama (nativ, R9700 32 GB + RX 7800 XT 16 GB) und Docker Desktop. Von aussen erreichbar über den
Traefik im [oryn-gateway](https://github.com/brandadrian/oryn-gateway): Er liest die Routing-Regeln aus den Labels der Container hier,
im oryn-gateway selbst stehen keine Regeln für diese Dienste.

| Adresse | Was |
|---------|-----|
| `https://ollama-api.oryn.brandadrian.com/v1` | OpenAI-kompatible API (Copilot, SDKs), Bearer-Key nötig |
| `https://ollama-api.oryn.brandadrian.com/api` | Ollama-API, Bearer-Key nötig (Alias: `api.oryn.brandadrian.com`) |
| `https://monitoring.oryn.brandadrian.com/monitor` | Grafana, öffentlich nur lesen (`/` leitet hierhin) |
| `https://chat.oryn.brandadrian.com` | Open WebUI (`openwebui/`) |
| `http://localhost:3000/monitor` | Grafana lokal mit Admin-Login |

Nur noch die oryn-Adressen sind öffentlich, die alten `*.homelab.brandadrian.com`-Adressen sind abgeschaltet.
Lokal (selbstsigniertes Zertifikat): `ollama.localhost` (API), `openwebui.localhost`, `ollama-monitoring.localhost/monitor`.
DNS: IONOS-CNAME `*.oryn` → `brandadrian.internet-box.ch`, Zertifikate holt Traefik pro Hostname (Let's Encrypt, HTTP-Challenge).

## Inhalt

- [System-Kontext](#system-kontext)
- [Struktur](#struktur)
- [Einrichten](#einrichten)
- [Erkenntnisse: Copilot, Cache und GPUs (2026-11-07)](#erkenntnisse-copilot-cache-und-gpus-2026-11-07)
- [Dokumentation](#dokumentation)

## System-Kontext

```mermaid
flowchart LR
    client([Copilot, Skripte<br/>mit API-Key])
    visitor([Besucher / Browser])

    subgraph ionos[IONOS DNS]
        dns["*.oryn.brandadrian.com<br/>CNAME → brandadrian.internet-box.ch"]
    end

    subgraph pc[Windows-PC]
        system["Windows-Leistungsindikatoren<br/>CPU, RAM, GPU, VRAM"]
        ollama[("Ollama nativ · GPU<br/>Modelle aus models/")]
        monitor["ollama-monitor/ OllamaMonitor<br/>Windows-Dienst"]

        subgraph docker["Docker Desktop · Netz proxy"]
            traefik["Traefik · HTTPS<br/>(oryn-gateway)"]
            subgraph api["api/"]
                nginx["nginx<br/>prüft API-Key"]
                meter["meter<br/>misst jede Anfrage"]
            end
            subgraph mon["monitoring/"]
                prom[(Prometheus)]
                loki[(Loki)]
                grafana["Grafana /monitor<br/>Dashboards"]
            end
        end
    end

    client -- "/v1, /api" --> dns --> traefik
    visitor -- "/monitor" --> dns
    traefik --> nginx --> meter --> ollama
    traefik -- "nur lesen" --> grafana
    meter -- "1 Zeile pro Anfrage<br/>Client, Modell, Tokens, Zeiten" --> loki
    system --> monitor
    ollama -- "/api/ps, server.log" --> monitor
    monitor -- "OTLP-Metriken" --> prom
    monitor -- "Log-Zeilen" --> loki
    prom --> grafana
    loki --> grafana
```

- **Dashboard "Ollama & Rechner":** Hardware, Auslastung, geladene Modelle, Tokens aller Clients (aus `server.log`, also auch Open WebUI und Saba).
- **Dashboard "Ollama API (Anfragen)":** nur Anfragen über diese API, dafür pro Anfrage mit Client, Modell, Cache und Zeiten.

## Struktur

```
api/             nginx (API-Key-Prüfung) + meter (Mess-Proxy, Node)        → docs/api.md
models/          Modelfiles der eigenen Modelle                            → docs/models.md
monitoring/      Prometheus, Loki, Grafana (Dashboards, Daten in data/)    → docs/monitoring.md
scripts/         ollama-gpu.ps1: Ollama-Karten umschalten (beide / nur R9700 / nur RX 7800 XT / ROCm) → docs/models.md
ollama-monitor/  OllamaMonitor (.NET 10, ollama-monitor.slnx): Windows-Dienst für Hardware + Ollama-Metriken,
                 Dockerfile für den optionalen Container (ohne Hardware-Werte)
openwebui/       Open WebUI: Chat und Modellverwaltung mit Login             → docs/openwebui.md
docs/            Detail-Dokumentation
```

## Einrichten

Voraussetzungen: Ollama nativ unter Windows, Docker Desktop, laufender [oryn-gateway](https://github.com/brandadrian/oryn-gateway)
(Traefik und Docker-Netz `proxy`), IONOS-CNAME `*.oryn` → `brandadrian.internet-box.ch`.

1. **Ollama auf Vulkan** umstellen (mit zwei verschiedenen AMD-Karten stürzt ROCm beim Verteilen eines Modells ab, Details in
   [docs/models.md](docs/models.md#backend-rocm-oder-vulkan)), PowerShell:

   ```powershell
   setx OLLAMA_VULKAN 1
   ```

   ```powershell
   setx HIP_VISIBLE_DEVICES -1
   ```

   Danach Ollama in der Taskleiste beenden und neu starten. Prüfen: in `%LOCALAPPDATA%\Ollama\server.log` stehen zwei Zeilen
   `inference compute … library=Vulkan` (R9700 und RX 7800 XT).

2. **Modelle** anlegen → [docs/models.md](docs/models.md)
3. **Monitoring** starten (zuerst, die API schreibt nach Loki):

   ```bash
   cd monitoring && docker compose up -d
   ```

4. **API** starten: `api/.env` aus `api/.env.example` erstellen, Key setzen (PowerShell: `[guid]::NewGuid()`), dann

   ```bash
   cd api && docker compose up -d
   ```

5. **OllamaMonitor als Windows-Dienst** → [docs/monitoring.md](docs/monitoring.md#ollamamonitor-als-windows-dienst)
6. **Open WebUI** starten: `openwebui/.env` aus `openwebui/.env.example`, dann `cd openwebui && docker compose up -d` → [docs/openwebui.md](docs/openwebui.md)

Nach dem ersten `docker compose up` prüfen, ob die Container in beiden Netzen hängen (`docker inspect <name>`).
Docker Desktop hängt beim ersten Start manchmal nur ein Netz an, dann `docker compose up -d --force-recreate`.

## Erkenntnisse: Copilot, Cache und GPUs (2026-11-07)

Anlass: GitHub Copilot (Incident-Analysen mit Loki/ES/GitLab/Prometheus) wartete minutenlang und brach ab.

### Aktuelles Setup

| | Wert |
|---|---|
| Copilot-Modell | `qwen3.6:27b-abx-rca-q4-128k` (Q4, 128k Kontext), nur R9700, 25 GB, 100 % GPU |
| Karten | Vulkan, nur R9700: `GGML_VK_VISIBLE_DEVICES=1`. Der Monitor hängt an der RX 7800 XT, siehe unten |
| Parallel | `OLLAMA_NUM_PARALLEL=2`: 2 Slots mit je 128k |
| Alternative genau | `qwen3.6:27b-abx-rca-128k` (Q8, 40/40 im Benchmark), braucht **beide** Karten (38 GB) |

Neue Modelfiles: `models/qwen3.6-27b-abx-rca-128k.Modelfile`, `models/qwen3.6-27b-abx-rca-q4-128k.Modelfile`.
Alle abx-rca-Systemprompts (und `incident-agent*` im incident-lab) haben jetzt die Regel: bei E2E-Tests zuerst Prometheus abfragen.

### Messwerte (Prompt mit ca. 31k Tokens, Vulkan)

| Setup | Einlesen | Ausgabe | VRAM |
|---|---|---|---|
| Q8 auf beiden Karten, automatische Aufteilung (ca. 2:1) | 1.057 t/s | 18,2 t/s (16 t/s bei 61k Kontext) | 38 GB |
| Q8, `LLAMA_ARG_TENSOR_SPLIT=3,1` | 165 t/s | 10 t/s | läuft über (3,5 GB im RAM) |
| Q8, `LLAMA_ARG_TENSOR_SPLIT=4,1` | 141 t/s | 7 t/s | läuft über (4,6 GB im RAM) |
| Q4 auf beiden Karten | 956 t/s | 26,6 t/s | 28 GB |
| **Q4 nur R9700** | 787 t/s | 29,2 t/s | 25 GB |
| qwen3.8:27b-agent (vorher), nur R9700 | ca. 800 t/s | ca. 60 t/s | 17 GB |

Die Genauigkeit von Q4 bei Incident-Analysen ist **noch nicht gemessen** (incident-lab-Benchmark offen). Q8 hatte 40/40,
qwen3.8 27B Q8 36/40, 35B-A3B höchstens 30–32/40.

### Was Copilot langsam gemacht hat

- **Ein Slot, zwei Unterhaltungen:** Copilot schickt neben dem Haupt-Chat eigene Anfragen (Subagent/Zusammenfassung) mit anderem
  Kontext (z. B. 54k und 38k Tokens). Mit `OLLAMA_NUM_PARALLEL=1` verdrängen sie sich gegenseitig den Cache, und jede Anfrage
  liest den ganzen Prompt neu ein (50–70 s). Nach **2 Minuten bricht Copilot ab** (nginx 499 / Ollama 500), schickt die Anfrage
  erneut, und alles beginnt von vorn. Abhilfe: `OLLAMA_NUM_PARALLEL=2`.
- **Kontext zu klein:** Die alte abx-rca-Variante hatte 32k, Copilot-Unterhaltungen haben 40–61k. Darum die 128k-Varianten.
- **Copilot-Grundlast:** Systemprompt und Tool-Definitionen ergeben ca. **26k Tokens pro Anfrage**. In Copilot nur die nötigen
  Tools (Loki, ES, GitLab, Prometheus) aktivieren. Im Benchmark fiel die Trefferquote mit 51 Tools auf 8/40.
- **Copilot ersetzt den SYSTEM-Prompt** aus dem Modelfile. Regeln für Copilot gehören in `.github/copilot-instructions.md`.
- **Slot-Wahl:** llama-server nimmt den Slot mit dem ähnlichsten Prompt-Anfang (Grenze 10 %). Weil Copilot-Anfragen 26k Tokens
  gemeinsam haben, landet eine Nebenanfrage oft im belegten Slot statt im freien. qwen3.6 ist ein Hybrid-Modell (rekurrente
  Layer), der Cache lässt sich nicht auf den gemeinsamen Anfang kürzen, dann wird alles neu eingelesen (`forcing full prompt
  re-processing` im Log). Verdrängte Slots landen im RAM-Prompt-Cache (8 GB) und Checkpoints fangen viel ab. Die Schwelle
  (`--slot-prompt-similarity`) lässt sich unter Ollama nicht per Variable setzen.
- Läuft der Cache, liest eine Folgeanfrage nur noch 66–2.800 neue Tokens ein (Sekunden). Dann bremst nur noch die Ausgabe.
- **Checkpoints helfen hier nicht (getestet):** Ein Checkpoint ist ein gespeicherter Zwischenstand, zu dem ein Hybrid-Modell
  zurückspringen kann, statt alles neu zu rechnen. llama-server legt sie nur **am Ende** eines Prompts an (Ende − 512 und Ende),
  nicht unterwegs. `LLAMA_ARG_CHECKPOINT_MIN_SPACING_NT=1024` (Standard 8192) regelt nur den Abstand zwischen diesen
  End-Checkpoints. Test: gleicher 20k-Anfang mit kurzem anderem Ende → 4,5 s statt 25 s (Checkpoint passt zufällig). Gleicher
  Anfang plus über 10k anderes Ende, wie bei Copilot → kein Checkpoint im gemeinsamen Teil, alles neu. Variable wieder entfernt.
  Folgeanfragen derselben Unterhaltung (wachsen nur hinten) sind schnell. Teuer bleibt nur der Wechsel zwischen Haupt-Chat
  und Copilot-Nebenanfrage.
- **Mögliche Alternativen (nicht umgesetzt, Entscheid 2026-11-07: so lassen):** llama-server direkt (statt Ollama) mit
  `--slot-prompt-similarity 0.9`, dann landen Copilot-Nebenanfragen im freien Slot. Bequem mit **llama-swap** als
  OpenAI-kompatiblem Proxy davor. LM Studio bietet nicht mehr Stellschrauben, vLLM/SGLang laufen nicht unter Windows/AMD.
  Agenten mit kleineren Prompts als Copilot: OpenCode, Aider, Continue (nicht gemessen).
- Sporadisch: `chat prompt error … An existing connection was forcibly closed` (Ollama 0.40.15, Verbindung zum eigenen
  llama-server). Kam auch bei eigenen Testanfragen, nicht Copilot-spezifisch. Der Client wiederholt die Anfrage.

### GPUs

- Bei Q8 auf beiden Karten ist die **RX 7800 XT der Engpass** (100 % Compute, R9700 ca. 55 %), obwohl sie nur ca. ein Drittel
  der Layer hat. Die Layer laufen nacheinander, die R9700 wartet.
- Ollama startet `llama-server` ohne `--tensor-split`. Der liest aber Umgebungsvariablen, z. B. `LLAMA_ARG_TENSOR_SPLIT`
  oder `LLAMA_ARG_FIT_TARGET` (Reserve pro Karte in MiB). Siehe `llama-server.exe --help` in
  `%LOCALAPPDATA%\Programs\Ollama\lib\ollama\`.
- **Monitor belegt VRAM:** Am Monitor hängende Karte: ca. 3–3,6 GB weg (Desktop + Programme). Darum lief jede Verschiebung zur
  R9700 über. Der Monitor ist jetzt an der RX 7800 XT, die R9700 hat 31,7 GB frei.
- **Vulkan-Reihenfolge ändert sich mit dem Monitor:** Die Karte mit dem Monitor wird `Vulkan0`. Jetzt: `Vulkan0` = RX 7800 XT,
  `Vulkan1` = R9700. Nach dem Umstecken stand `GGML_VK_VISIBLE_DEVICES=0` noch auf dem alten Wert, und Q8 lief zu 58 % auf
  der CPU. Prüfen im `server.log`: `using device Vulkan0 (…)`.
- Q8 (26 GB + 8,7 GB Cache) passt **nicht** allein auf die R9700, Q4 (15 GB + 8,7 GB) schon.
- Der i5-13600KF hat keine integrierte Grafik, den Monitor kann also nur eine der Karten übernehmen.

### VRAM-Bedarf berechnen

Faustformel: `VRAM ≈ Gewichte + KV-Cache + ca. 1–2 GB Overhead`

- **Gewichte** = Parameter × Bits ÷ 8. Für 27B: Q4 (Q4_K_M ≈ 4,8 Bit) ≈ 16 GB, Q8 (≈ 8,5 Bit) ≈ 29 GB.
- **KV-Cache** wächst linear mit dem Kontext (2 × Layer × KV-Heads × Head-Dim × Kontext × 2 Byte). Einfacher ablesen:
  Q4 mit 131k belegt ca. 25–26 GB, der Cache macht also ca. 9–10 GB bei 128k aus (`KV buffer size` im `server.log`).
- **Beispiel Q8 mit 128k:** 29 + 10 + 2 ≈ 41 GB. Passt nicht allein auf die R9700 (32 GB), aber auf beide Karten (48 GB).
- **Aber:** Beim Split bremst die RX 7800 XT, weil die Karten ihre Layer nacheinander rechnen. Q8 auf beiden Karten ist
  daher langsamer als Q4 allein auf der R9700. Prüfen mit `ollama ps`: Dort muss „100% GPU“ stehen.

### Stolpersteine

- Ollama neu starten aus einer Shell: Die Taskleisten-App übernimmt die Variablen **dieser Shell**, nicht die gespeicherten
  Benutzervariablen. Eine alte Shell startet Ollama z. B. mit `OLLAMA_NUM_PARALLEL=1` oder ohne `HIP_VISIBLE_DEVICES`.
  Vorher alle Variablen aus `[Environment]::GetEnvironmentVariable(…, 'User')` in die Shell laden (oder neue Shell).
  `scripts/ollama-gpu.ps1` lädt aktuell nur die drei GPU-Variablen.
- Beim Neustart hat Ollama sich selbst aktualisiert (0.40.13 → 0.40.15), Einstellungen blieben erhalten.
- Nützliche Log-Muster in `%LOCALAPPDATA%\Ollama\server.log`: `new prompt`, `prompt eval time`, `eval time`,
  `selected slot by LCP similarity`, `forcing full prompt`, `model buffer size`, `KV buffer size`, `msg="server config"`.

## Dokumentation

| Thema | Datei |
|-------|-------|
| API: Zugang, Endpunkte, Clients, Anfragen auswerten und optimieren | [docs/api.md](docs/api.md) |
| Modelle: welche, wofür, Benchmarks, GPU-Planung | [docs/models.md](docs/models.md) |
| Monitoring: Dashboards, OllamaMonitor-Dienst, öffentliches Grafana | [docs/monitoring.md](docs/monitoring.md) |
| Open WebUI: Chat, Modelle verwalten, Benutzer | [docs/openwebui.md](docs/openwebui.md) |
| Basics: Instructions/Skills/Agents, Modelfile-SYSTEM, num_ctx, Performance | [docs/basics.md](docs/basics.md) |
