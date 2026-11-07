# Modelle

[← zurück zur README](../README.md)

Ollama läuft nativ unter Windows auf der GPU. Eigene Varianten entstehen aus den Modelfiles in `models/`.
Namenskonvention: `familie:grösse-zweck`, z.B. `qwen3.8:27b-agent` (Basis erkennbar, Suffix = Zweck).

## Installiert

GPU: AMD Radeon AI PRO R9700 (32 GB, ROCm). Messung 2026-11-05, alle Modelle 100 % auf der GPU.

| Modell | Wofür | Prompt / Ausgabe | VRAM |
|--------|-------|------------------|------|
| `qwen3.8:27b-agent` | Agenten, Tool-Calls, Copilot. temperature 0.3, 128k Kontext. [Modelfile](../models/qwen3.8-27b-agent.Modelfile) | 656 / 40 t/s | 18 GB |
| `qwen3.8:27b-agent-q6` | wie oben, Q6_K_XL: genauer, langsamer. [Modelfile](../models/qwen3.8-27b-agent-q6.Modelfile) | 621 / 21 t/s | 30 GB |
| `qwen3.8:27b` | Code und Analysen im Chat (gleiche Dateien wie `-agent`) | 1000 / 41 t/s | 18 GB |
| `gpt-oss:20b` | schneller Chat, schwierige Fragen | 3600 / 102 t/s | 13 GB |
| `qwen3.5:9b` | schnell und klein, versteht Bilder | 3550 / 79 t/s | 8,6 GB |
| `qwen3-vl:8b-instruct` | Bilder und Rechnungen auslesen | | 6 GB |
| `qwen3.6:27b-abx-rca` | Incident-Analyse ES → Loki → GitLab, **genau**: 40/40 im incident-lab. temperature 0, 32k. Braucht R9700 + RX 7800 XT. [Modelfile](../models/qwen3.6-27b-abx-rca.Modelfile) | ~1000 / 19 t/s | 33 GB (beide Karten) |
| `qwen3.6:35b-a3b-abx-rca` | Incident-Analyse, **schnell**: 30–32/40. temperature 0.7, top_p 0.8, 64k. Nur R9700. [Modelfile](../models/qwen3.6-35b-a3b-abx-rca.Modelfile) | ~3300 / 135 t/s | 26 GB |

Die zwei `-abx-rca`-Modelle (MCP-Agent für ES → Loki → GitLab) sind mit dem incident-lab (`C:\github\incident-lab`, Ergebnisse in `docs/tuning.md`, 21 Läufe am 2026-11-07)
abgestimmt. Wichtiger als die Parameter: nur ES/Loki/GitLab-Tools anbieten (mit 40 Zusatz-Tools 8/40), Datum + Zeitzone in die Anfrage,
Tool-Ausgaben auf ~2.000 Zeichen kürzen, keine Beispieldaten in Tool-Beschreibungen. Ihr `SYSTEM`-Prompt greift nur, wenn der
Client keinen eigenen schickt.

`gemma3:27b` und `saba` gehören zum Saba-Chat im homelab-proxy.

## Anlegen / aktualisieren

```powershell
ollama create qwen3.8:27b-agent -f models/qwen3.8-27b-agent.Modelfile
```

```powershell
ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL
```

```powershell
ollama create qwen3.8:27b-agent-q6 -f models/qwen3.8-27b-agent-q6.Modelfile
```

```powershell
ollama create qwen3.6:27b-abx-rca -f models/qwen3.6-27b-abx-rca.Modelfile
```

```powershell
ollama create qwen3.6:35b-a3b-abx-rca -f models/qwen3.6-35b-a3b-abx-rca.Modelfile
```

Gilt ab der nächsten Anfrage, kein Neustart nötig. Kein `SYSTEM`-Prompt in Agent-Modellen: Copilot schickt eigene Anweisungen,
ein fester Agent-Ablauf hat im Test falsche Tool-Calls verursacht. Ausnahme: die `-abx-rca`-Modelle haben einen kurzen
Standard-Prompt, im incident-lab war ein System-Prompt Pflicht (ohne: 23/40).

## Q4 gegen Q6 (2026-11-05)

Gleiche Aufgaben: 110k-Token-Log mit 6 versteckten Fakten, 9 Tool-Calls (LogQL, Elasticsearch-DSL).

| | Q4_K_M | UD-Q6_K_XL |
|---|---|---|
| Ausgabe | 40 t/s | 21 t/s |
| Prompt einlesen | 656 t/s | 621 t/s |
| Fakten aus 110k Tokens | 6/6 | 6/6 |
| Tool-Calls | 6/9 (ES-Body als String statt Objekt) | 7/9 (Fehler war gültiges LogQL) |

Q6 ist bei Tool-Calls sauberer, schreibt aber halb so schnell. Bei grossen Copilot-Kontexten dominiert das Einlesen, dort ist der Unterschied klein.
In der Ollama-Library gibt es qwen3.8 nur als Q4_K_M und Q8_0, Q6 kommt von unsloth (Hugging Face).

## Kontext und VRAM

KV-Cache (`OLLAMA_KV_CACHE_TYPE=q8_0`, Flash Attention): ca. 1,1 GB pro 32k Tokens bei Qwen 3.8 27B. Das Modell kann nativ 256k.

| Variante | Modell | 128k | 256k | passt in |
|---|---|---|---|---|
| Q4_K_M | 18 GB | ~23 GB | ~27 GB | R9700 |
| UD-Q6_K_XL | 26 GB | ~30 GB | ~35 GB | R9700 nur 128k, 256k mit RX 7800 XT |
| Q8_0 | 29 GB | ~34 GB | ~38 GB | nur mit RX 7800 XT |

Mit zweiter Karte (RX 7800 XT, 16 GB, zusammen 48 GB) gibt es zwei Wege:

- **Zwei Modelle parallel:** Agent auf der R9700, zweites Modell (z.B. `gpt-oss:20b`) auf der 7800 XT. Ollama legt ein Modell, das auf eine Karte passt, ganz auf diese Karte.
- **Ein Modell maximal:** Q6/Q8 mit 256k über beide Karten verteilt. Nicht schneller, aber mehr Kontext.

Ollama-Einstellungen (Windows-Benutzervariablen): `OLLAMA_CONTEXT_LENGTH=131072`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_VULKAN=true`.
