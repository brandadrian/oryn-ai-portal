# Modelle

[← zurück zur README](../README.md)

Ollama läuft nativ unter Windows auf der GPU. Eigene Varianten entstehen aus den Modelfiles in `models/`.
Namenskonvention: `familie:grösse-zweck`, z.B. `qwen3.8:27b-agent` (Basis erkennbar, Suffix = Zweck).

## Installiert

GPUs: AMD Radeon AI PRO R9700 (32 GB) + RX 7800 XT (16 GB). Ollama nutzt zurzeit **nur die R9700** (`GGML_VK_VISIBLE_DEVICES=1`),
die 7800 XT treibt den Monitor. Stand 2026-11-08, Benchmarks: incident-lab (`C:githubincident-labdocs	uning.md`) und
coding-lab (`C:githubcoding-labREADME.md`).

### Nach Use Case

Jedes Modelfile hat in der ersten Zeile `# USE CASE: … | Variante: … | Status: …`.

| Use Case | Modell | Einstellungen | Getestet | Ausgabe | VRAM |
|---|---|---|---|---|---|
| **Incident-Analyse** (ES → Loki → GitLab, Copilot) | `qwen3.8:27b-abx-rca-q4-128k` · [Modelfile](../models/qwen3.8-27b-abx-rca-q4-128k.Modelfile) | **empfohlen**: temp 0, 128k, Incident-Prompt | ✅ 39/40 | ~57 t/s | 19 GB |
| | `qwen3.6:27b-abx-rca-q4-128k` · [Modelfile](../models/qwen3.6-27b-abx-rca-q4-128k.Modelfile) | temp 0, 128k | ✅ 37/40 | ~32 t/s | 23 GB |
| | `qwen3.6:27b-abx-rca` · [Modelfile](../models/qwen3.6-27b-abx-rca.Modelfile) | Q8, 32k (passt allein auf R9700) | ✅ 40/40 | ~16 t/s | 29 GB |
| | `qwen3.6:27b-abx-rca-128k` · [Modelfile](../models/qwen3.6-27b-abx-rca-128k.Modelfile) | Q8, 128k, nur mit beiden Karten | (40/40 bei 32k) | ~18 t/s | 39 GB |
| | `qwen3.6:35b-a3b-abx-rca` · [Modelfile](../models/qwen3.6-35b-a3b-abx-rca.Modelfile) | schnell (MoE), temp 0.7, 64k | ✅ 30–32/40 | ~135 t/s | 26 GB |
| **Coding** | `qwen3.8:27b-coding-q4-128k` · [Modelfile](../models/qwen3.8-27b-coding-q4-128k.Modelfile) | temp 0, 128k, **ohne System-Prompt** | ✅ 10/10 | ~57 t/s | 19 GB |
| **Recherche mit Websuche** | `qwen3.8:27b-research-q4-128k` · [Modelfile](../models/qwen3.8-27b-research-q4-128k.Modelfile) | temp 0.6, 128k, Recherche-Prompt; in Open WebUI Websuche an (Brave, 6 Treffer) | ✅ Kurztest 4/4 | ~57 t/s | 19 GB |
| **Allgemeiner Agent** | `qwen3.8:27b-agent` · [Modelfile](../models/qwen3.8-27b-agent.Modelfile) | temp 0.3, 128k | Test 05.11. | ~57 t/s | 19 GB |
| **Dokumente / Rechnungen** | `qwen3-vl:32b-instruct` | Bilder/PDF-Seiten auslesen, mit `num_ctx` 16–32k anfragen | – | | 21 GB |
| | `qwen3-vl:8b-instruct` | einfache Belege, schnell | – | | 6 GB |
| **Chat** | `gpt-oss:20b` | schnell, schwierige Fragen | nur Tempo | ~102 t/s | 13 GB |
| | `qwen3.5:9b` | klein, versteht Bilder | nur Tempo | ~79 t/s | 8,6 GB |

Basismodelle (in Open WebUI ausgeblendet): `qwen3.8:27b`, `qwen3.6:27b-q8_0`, `qwen3.6:27b-q4_K_M`, `qwen3.6:35b-a3b-q4_K_M`.

qwen3.8 schreibt rund doppelt so schnell wie qwen3.6, weil es **Multi-Token-Prediction** nutzt (`draft_num_predict 4`, im Basismodell
enthalten): ein kleiner Zusatzkopf rät bis zu 4 Tokens voraus, das grosse Modell prüft sie in einem Durchgang (~76 % Treffer im Benchmark).
Das kostet keine Genauigkeit. Achtung: qwen3.8 hat andere Defaults als qwen3.6 (`presence_penalty 0`, `temperature 1`), deshalb setzen
die Modelfiles diese Werte explizit.

Wichtiger als die Parameter (incident-lab): nur ES/Loki/GitLab-Tools anbieten (mit 40 Zusatz-Tools 8/40), Datum + Zeitzone in die Anfrage,
Tool-Ausgaben auf ~2.000 Zeichen kürzen, keine Beispieldaten in Tool-Beschreibungen. Der `SYSTEM`-Prompt im Modelfile greift nur,
wenn der Client keinen eigenen schickt (Copilot ersetzt ihn).

## Anlegen / aktualisieren

```powershell
ollama create qwen3.8:27b-abx-rca-q4-128k -f models/qwen3.8-27b-abx-rca-q4-128k.Modelfile
```

```powershell
ollama create qwen3.8:27b-coding-q4-128k -f models/qwen3.8-27b-coding-q4-128k.Modelfile
```

```powershell
ollama create qwen3.8:27b-research-q4-128k -f models/qwen3.8-27b-research-q4-128k.Modelfile
```

Analog für die übrigen Modelfiles in `models/`. Dauert Sekunden, nichts wird neu geladen, die Dateien des Basismodells werden geteilt.
Gilt ab der nächsten Anfrage. Ist das Modell gerade geladen, sicherheitshalber vorher `ollama stop <name>`. Prüfen mit
`ollama show <name> --modelfile`.

Beim Ändern beachten: `#` kommentiert nur eine Zeile. Ein mehrzeiliger `SYSTEM """…"""`-Block muss auf **allen** Zeilen
auskommentiert werden, sonst bricht `ollama create` ab. Ohne `SYSTEM` gibt es gar keinen System-Prompt (die Basismodelle haben keinen).
In Open WebUI kann pro Modell ein eigener System-Prompt hinterlegt sein, der hat Vorrang (z.B. beim Recherche-Modell mit `{{CURRENT_DATE}}`).

## Laden, Wechseln, Keep-Alive

- `ollama ps`: welche Modelle gerade geladen sind (VRAM/RAM, CPU/GPU-Anteil, Kontext). `ollama stop <name>` entlädt, löscht nichts.
- `ollama list`: installierte Modelle. `ollama rm <name>` löscht.
- **Neu geladen wird nur bei anderen Modelldateien oder anderem Kontext (`num_ctx`).** Temperatur, System-Prompt usw. ändern nichts.
  Deshalb haben alle qwen3.8-Varianten 128k: `-abx-rca-q4-128k`, `-coding-q4-128k`, `-research-q4-128k` und `-agent` teilen sich
  **ein geladenes Modell** (19 GB). Gemessen: erstes Laden 20 s, Wechsel danach 0 s. Wechsel zu qwen3.6 oder qwen3-vl = neu laden.
- Fragt ein Client ein anderes `num_ctx` an (z.B. der document-processor 32k), wird ebenfalls neu geladen.
- **Keep-Alive** (`OLLAMA_KEEP_ALIVE`, seit 2026-11-08 `24h`): wie lange ein Modell nach der letzten Anfrage geladen bleibt.
  Werte: Dauer wie `10m`, `2h`, `24h` oder Sekunden (`3600`); **`-1` = für immer geladen**; `0` = sofort entladen.
  Pro Anfrage überschreibbar mit `"keep_alive"` im API-Aufruf. Ändern (danach Ollama neu starten):

  ```powershell
  [Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "24h", "User")
  ```

  Neustart so, dass Ollama die Benutzer-Variablen sieht (sonst erbt es die Umgebung der aufrufenden Shell): Ollama im Tray beenden
  und neu starten, oder PowerShell neu öffnen und dann `ollama app.exe` starten.

  **Warum 24h:** Die R9700 ist nur für Ollama da (Monitor an der 7800 XT), der VRAM fehlt also niemandem. Ohne Keep-Alive
  dauert die erste Anfrage nach einer Pause ~20 s Laden, und Copilots Prompt-Cache geht verloren. Kosten: ~19 GB VRAM dauerhaft belegt,
  ein paar Watt mehr im Leerlauf.

  **Selbst entladen** (`ollama stop <name>`) ist nur nötig, um die R9700 für etwas ausserhalb von Ollama freizumachen (z.B. Spiele) oder wenn ein
  Modell mit CPU-Anteil viel System-RAM festhält (`ollama ps` zeigt dann z.B. `36%/64% CPU/GPU`). Wechsel zwischen Ollama-Modellen
  regelt Ollama selbst: das alte wird verdrängt, sobald der Platz fehlt, auch bei `-1`.

  `-1` (für immer) ist nicht gefährlich, aber ein versehentlich zu gross geladenes Modell (falsches `num_ctx`) bleibt dann im RAM hängen,
  bis man es stoppt. Mit `24h` räumt es sich spätestens nach einem Tag selbst weg.
- Mit `OLLAMA_NUM_PARALLEL=2` reserviert Ollama Kontext-Speicher für 2 Anfragen gleichzeitig (KV × 2). Bei grossen Modellen mit 128k
  kann das den Unterschied zwischen "passt" und "läuft teilweise auf der CPU" ausmachen (27B Q8 128k: 39 GB → 21 % CPU).

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
`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KEEP_ALIVE=24h`.

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

### Karten umschalten (Skript)

[`scripts/ollama-gpu.ps1`](../scripts/ollama-gpu.ps1) setzt die Variablen, startet Ollama neu und zeigt laut `server.log`, welche Karten aktiv sind:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode status   # nur anzeigen
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode both     # Vulkan, beide Karten (Standard)
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode r9700    # Vulkan, nur R9700
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode rx       # Vulkan, nur RX 7800 XT
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode rocm     # zurück auf ROCm
powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode restart  # nur neu starten, Einstellungen bleiben
```

Nur eine Karte schränkt Ollama über `GGML_VK_VISIBLE_DEVICES` ein; den Index (Vulkan0/Vulkan1) liest das Skript aus dem `server.log`.
Der Neustart entlädt alle Modelle, laufende Anfragen (API, Open WebUI) brechen ab. `qwen3.6:27b-abx-rca` braucht beide Karten
(nur auf der R9700 lagert er in den System-RAM aus und wird sehr langsam).
