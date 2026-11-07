# Modelle

[← zurück zur README](../README.md)

Ollama läuft nativ unter Windows auf der GPU. Eigene Varianten entstehen aus den Modelfiles in `models/`.
Namenskonvention: `familie:grösse-zweck`, z.B. `qwen3.8:27b-agent` (Basis erkennbar, Suffix = Zweck).

## Installiert

GPUs: AMD Radeon AI PRO R9700 (32 GB) + RX 7800 XT (16 GB), zusammen 48 GB. Modelle, die auf eine Karte passen, legt Ollama
ganz auf eine Karte; grössere (z.B. 27B Q8) verteilt es auf beide. Messungen 2026-11-05 (nur R9700) bzw. 2026-11-07, alle Modelle 100 % auf der GPU.

### Nach Use Case

Jedes Modelfile hat in der ersten Zeile `# USE CASE: … | Variante: … | Status: …`.

| Use Case | Modell | Variante | Getestet | Prompt / Ausgabe | VRAM |
|---|---|---|---|---|---|
| **Incident-Analyse / Root Cause** (ES → Loki → GitLab) | `qwen3.6:27b-abx-rca` · [Modelfile](../models/qwen3.6-27b-abx-rca.Modelfile) | genau (empfohlen): temperature 0, 32k, beide Karten, **Vulkan** | ✅ incident-lab 40/40 | ~1000 / 19 t/s | 33 GB |
| | `qwen3.6:35b-a3b-abx-rca` · [Modelfile](../models/qwen3.6-35b-a3b-abx-rca.Modelfile) | schnell: temperature 0.7, top_p 0.8, 64k, nur R9700, **Vulkan** | ✅ incident-lab 30–32/40 | ~3300 / 135 t/s | 26 GB |
| **Allgemeiner Agent / Copilot** (Tool-Calls) | `qwen3.8:27b-agent` · [Modelfile](../models/qwen3.8-27b-agent.Modelfile) | Standard (Q4): temperature 0.3, 128k | Test 05.11. (nicht im incident-lab) | 656 / 40 t/s | 18 GB |
| | `qwen3.8:27b-agent-q6` · [Modelfile](../models/qwen3.8-27b-agent-q6.Modelfile) | genau (Q6_K_XL), langsamer | Test 05.11. | 621 / 21 t/s | 30 GB |
| **Coding** | *noch offen* (`qwen3.8:27b` vorerst) | – | – | 1000 / 41 t/s | 18 GB |
| **Chat** | `gpt-oss:20b` | schnell, schwierige Fragen | nur Tempo | 3600 / 102 t/s | 13 GB |
| | `qwen3.5:9b` | klein, versteht Bilder | nur Tempo | 3550 / 79 t/s | 8,6 GB |
| **Bilder / Rechnungen** | `qwen3-vl:8b-instruct` | Inhalte auslesen | – | | 6 GB |

Die zwei `-abx-rca`-Modelle (MCP-Agent für ES → Loki → GitLab) sind mit dem incident-lab (`C:\github\incident-lab`, Ergebnisse in `docs/tuning.md`, 21 Läufe am 2026-11-07)
abgestimmt. Wichtiger als die Parameter: nur ES/Loki/GitLab-Tools anbieten (mit 40 Zusatz-Tools 8/40), Datum + Zeitzone in die Anfrage,
Tool-Ausgaben auf ~2.000 Zeichen kürzen, keine Beispieldaten in Tool-Beschreibungen. Ihr `SYSTEM`-Prompt greift nur, wenn der
Client keinen eigenen schickt. Getestet wurde der 27B mit Vulkan über beide Karten (siehe [Backend](#backend-rocm-oder-vulkan)).
Zum Vergleich mit gleichen Einstellungen: `qwen3.8:27b-q8_0` kam auf 36/40 (Partner-Hostkey-Fall verfehlt, mehr Wiederholungen, 25 statt 20,5 min),
deshalb bleibt qwen3.6 27B die Basis für `-abx-rca`.

`gemma3:27b` und `saba` gehörten zum Saba-Chat, der entfernt wird; beide können danach mit `ollama rm` weg.

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

Ollama-Einstellungen (Windows-Benutzervariablen): `OLLAMA_VULKAN=1`, `HIP_VISIBLE_DEVICES=-1` (seit 2026-11-07), `OLLAMA_CONTEXT_LENGTH=131072`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KEEP_ALIVE=30m`.

## Backend: ROCm oder Vulkan

Ollama nimmt standardmässig ROCm. Mit zwei verschiedenen Karten (R9700 = gfx1201, RX 7800 XT = gfx1101) gilt (Tests 2026-11-07):

- **ROCm** stürzt mit `qwen3.6:35b-a3b` ab, sobald das Modell auf beide Karten verteilt wird (`ROCm error: no kernel image`, ab ~2k Prompt-Tokens).
  Nur auf der R9700 läuft es stabil. Der 27B lief mit ROCm über beide Karten in kurzen Tests.
- **Vulkan** läuft mit allen Modellen stabil über beide Karten und war beim 35B sogar schneller (~93 statt ~70 t/s).
  Der Benchmark (40/40 mit dem 27B) lief mit Vulkan.

Vulkan dauerhaft einschalten (PowerShell, danach Ollama in der Taskleiste beenden und neu starten):

```powershell
setx OLLAMA_VULKAN 1
```

```powershell
setx HIP_VISIBLE_DEVICES -1
```

`OLLAMA_VULKAN=1` allein reicht nicht, Ollama nimmt bei unterstützten Karten sonst trotzdem ROCm; `HIP_VISIBLE_DEVICES=-1` blendet ROCm aus.
Zurück zu ROCm: `reg delete HKCU\Environment /v OLLAMA_VULKAN /f` und `reg delete HKCU\Environment /v HIP_VISIBLE_DEVICES /f`, Ollama neu starten.
