# GPU-Benchmark: R9700 in PCIe-Slot 1 vs. Slot 2

Frage: Wie stark bremst es die AI PRO R9700, wenn sie statt im ersten Slot (PCIe 5.0 x16, CPU) im zweiten Slot (PCIe 4.0 x4, Chipsatz) steckt?

## System

- i5-13600KF, MSI MAG Z790 Tomahawk WiFi, 32 GB DDR5
- AMD Radeon AI PRO R9700 (32 GB) und RX 7800 XT (16 GB)
- Ollama 0.40.16, Vulkan, Split-Modus (`scripts/ollama-gpu.ps1 -Mode split`): R9700 auf Port 11434, RX 7800 XT auf 11435
- `OLLAMA_NUM_PARALLEL=1`, KV-Cache `q8_0`

## Was gemessen wird

Skript: `scripts/bench-gpu.ps1`, Laufzeit etwa 3,5 min. Die Zahlen kommen aus den Laufzeitwerten der Ollama-API (`load_duration`, `prompt_eval_*`, `eval_*`).

| Test | Ablauf | Aussage |
|---|---|---|
| Laden | Modell entladen und neu laden, 2x (Median). Ein Vorlauf füllt vorher den Windows-Dateicache, damit aus dem RAM geladen wird. | Upload in den VRAM, am ehesten PCIe-abhängig |
| Kurz | ~50 Tokens Prompt, bis 256 Tokens Antwort, 3x (Median) | typisches Chat-Gefühl |
| Lang | ~24k Tokens Prompt (Messprotokoll), 128 Tokens Antwort | Verarbeitung großer Kontexte |

Reproduzierbarkeit: Temperatur 0, Seed 42, `think=false`. Jeder Prompt bekommt eine Zufallskennung, damit Ollama keinen Prefix-Cache wiederverwendet.

Modelle: `qwen3.5:35b-a3b-q4-256k` (MoE, MTP) und `qwen3.8:27b-q4-128k` (dicht, MTP).

## Ausführen

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Label slot1-x16
powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Label slot2-x4
powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Compare slot1-x16,slot2-x4
```

Nach einem Kartentausch zuerst `ollama-gpu.ps1 -Mode both`, dann `-Mode split` ausführen. Die Vulkan-Indizes der Karten können sich ändern.

Ergebnisse als JSON: `bench/results/<Label>.json`.

## Ergebnisse

### Lauf 1: Slot 1, PCIe 5.0 x16 (19.11.2026)

| Modell | Laden | Prompt kurz | Gen kurz | Prompt 24k | Gen 24k |
|---|---|---|---|---|---|
| qwen3.5:35b-a3b | 26,8 s | 516 t/s | 125,5 t/s | 3096 t/s | 114,4 t/s |
| qwen3.8:27b | 18,9 s | 273 t/s | 44,5 t/s | 979 t/s | 44,6 t/s |

### RX 7800 XT im zweiten Slot (PCIe 4.0 x4), 19.11.2026

Die 35B und 27B passen nicht in 16 GB, deshalb lief hier `qwen3.5:9b` (7,4 GB VRAM, Port 11435, Label `rx7800-slot2`). Windows meldet für die Karte Gen4 x16. Das ist der Link der karteninternen PCIe-Bridge, nicht der des Slots.

| Modell | Laden | Prompt kurz | Gen kurz | Prompt 24k | Gen 24k |
|---|---|---|---|---|---|
| qwen3.5:9b | 8,2 s | 417 t/s | 74,2 t/s | 1135 t/s | 66,9 t/s |

### Beide Karten zusammen (R9700 Slot 1 + RX 7800 XT Slot 2), 19.11.2026

`ollama-gpu.ps1 -Mode both` mit `OLLAMA_SCHED_SPREAD=1`, damit Ollama jedes Modell auf beide Karten verteilt (sonst bliebe es auf der R9700). Label `both-r9700s1-rx7800s2`.

| Modell | Laden | Prompt kurz | Gen kurz | Prompt 24k | Gen 24k |
|---|---|---|---|---|---|
| qwen3.5:35b-a3b | 28,7 s | 439 t/s | 103,4 t/s | 2593 t/s | 79,6 t/s |
| qwen3.8:27b | 20,0 s | 213 t/s | 39,7 t/s | 648 t/s | 43,2 t/s |

Im Vergleich zur R9700 allein ist das überall langsamer: Gen kurz −18 % (35B) bzw. −11 % (27B), Gen 24k −30 % bzw. −3 %, Prompt 24k −16 % bzw. −34 %. Die Daten müssen zwischen den Karten über den Chipsatz-Link laufen, und die RX 7800 XT ist die langsamere Karte. Beide Karten zusammen lohnen sich nur für Modelle, die nicht in die 32 GB der R9700 passen.

### Große Q8-Modelle auf beiden Karten (48 GB), 19.11.2026

Modelle, die nicht in die 32 GB der R9700 allein passen. Gleiches Setup wie oben (`-Mode both`, `OLLAMA_SCHED_SPREAD=1`, Kontext 131072), Label `both-q8`. Beide Modelle zu 100 % auf den GPUs (66/66 Layer).

| Modell | VRAM | Laden | Prompt kurz | Gen kurz | Prompt 24k | Gen 24k |
|---|---|---|---|---|---|---|
| qwen3.5:35b-a3b-q8_0 | 36,7 GB | 48,2 s | 425 t/s | 95,0 t/s | 4231 t/s | 85,4 t/s |
| qwen3.8:27b-mtp-q8_0 | 30,0 GB | 31,0 s | 193 t/s | 31,7 t/s | 630 t/s | 28,8 t/s |

- Das 35B in Q8 ist auf beiden Karten nur 8 % langsamer (Gen kurz) als dasselbe Modell in Q4 verteilt, bei besserer Qualität. Beim 24k-Prompt war es sogar am schnellsten von allen Läufen.
- Das 27B in Q8 erreicht 32 t/s (16.11.: 27,5 t/s, damals mit 42k-Prompt).
- Beim 27B Q8 brach der Runner im ersten Versuch beim 24k-Prompt ohne Fehlermeldung ab (HTTP 500). Der zweite Versuch lief sauber durch; die 24k-Werte stammen aus diesem Einzelaufruf und sind nicht in `both-q8.json`.
- Die Ladezeit ist etwa 0,8 GB/s. Bei 38 GB passt das Modell nicht mehr ganz in den Dateicache (32 GB RAM).

### 70B auf beiden Karten, 20.11.2026

`llama3.3:70b` (Q4_K_M, 42 GB Datei), 81/81 Layer auf den GPUs, 42,5 GB VRAM. Wegen des knappen Speichers mit `-NumCtx 16384 -LongLines 450` (langer Prompt ~11k statt 24k Tokens). Label `both-70b`.

| Modell | Laden | Prompt kurz | Gen kurz | Prompt 11k | Gen 11k |
|---|---|---|---|---|---|
| llama3.3:70b | 51,5 s | 159 t/s | 13,6 t/s | 477 t/s | 12,7 t/s |

Läuft, aber mit 13,6 t/s nur etwa Lesetempo, und mehr als ~16k Kontext passt nicht. Dichte 70B-Modelle sind auf diesem Setup eher ein Grenzfall. Das 35B-A3B Q8 (95 t/s) ist das deutlich praktischere große Modell.

## Nach dem Kartentausch (20.11.2026)

R9700 jetzt im zweiten Slot (PCIe 4.0 x4 über Chipsatz), RX 7800 XT im ersten Slot (CPU). Geprüft über den PCIe-Baum in Windows: Die R9700 hängt am Chipsatz-Root-Port (Intel 7A30), die RX 7800 XT am CPU-Root-Port (Intel A70D). Die "Gen5 x16"/"Gen4 x16" im Skript-Header sind nur der Link der karteninternen Bridge und sagen nichts über den Slot. Vulkan-Indizes blieben gleich. Gleiche Tests, Labels mit `slot2-x4`, `rx7800-slot1`, `*-swapped`.

### R9700 allein: Slot 1 (x16) gegen Slot 2 (x4)

| Modell | Wert | Slot 1 x16 | Slot 2 x4 | Diff |
|---|---|---|---|---|
| qwen3.5:35b-a3b | Laden | 26,8 s | 24,8 s | −7 % (schneller) |
| | Prompt kurz | 516 t/s | 525 t/s | +2 % |
| | Gen kurz | 125,5 t/s | 125,5 t/s | 0 % |
| | Prompt 24k | 3096 t/s | 3048 t/s | −2 % |
| | Gen 24k | 114,4 t/s | 110,0 t/s | −4 % |
| qwen3.8:27b | Laden | 18,9 s | 17,5 s | −7 % (schneller) |
| | Prompt kurz | 273 t/s | 248 t/s | −9 % |
| | Gen kurz | 44,5 t/s | 44,4 t/s | 0 % |
| | Prompt 24k | 979 t/s | 973 t/s | −1 % |
| | Gen 24k | 44,6 t/s | 42,3 t/s | −5 % |

### RX 7800 XT allein (qwen3.5:9b): Slot 2 (x4) gegen Slot 1 (x16)

| Wert | Slot 2 x4 | Slot 1 x16 | Diff |
|---|---|---|---|
| Laden | 8,2 s | 8,0 s | −3 % |
| Prompt kurz | 417 t/s | 511 t/s | +23 % |
| Gen kurz | 74,2 t/s | 81,1 t/s | +9 % |
| Prompt 24k | 1135 t/s | 1349 t/s | +19 % |
| Gen 24k | 66,9 t/s | 72,6 t/s | +9 % |

Die RX 7800 XT ist im ersten Slot spürbar schneller, auch bei der Generierung, die kaum über PCIe läuft. Möglich ist, dass sie vorher am Chipsatz zusätzlich den Monitor bedient hat oder anders getaktet war. Ein einzelner Lauf, daher mit Vorsicht.

### Beide Karten verteilt: vorher (R9700 x16) gegen nachher (R9700 x4)

| Modell | Wert | vorher | nachher | Diff |
|---|---|---|---|---|
| qwen3.5:35b-a3b Q4 | Gen kurz | 103,4 t/s | 102,9 t/s | 0 % |
| | Prompt 24k | 2593 t/s | 2401 t/s | −7 % |
| qwen3.8:27b Q4 | Gen kurz | 39,7 t/s | 38,7 t/s | −3 % |
| | Prompt 24k | 648 t/s | 632 t/s | −2 % |
| qwen3.5:35b-a3b Q8 | Laden | 48,2 s | 41,5 s | −14 % (schneller) |
| | Gen kurz | 95,0 t/s | 91,5 t/s | −4 % |
| | Prompt 24k | 4231 t/s | 4252 t/s | 0 % |
| qwen3.8:27b Q8 | Gen kurz | 31,7 t/s | 32,0 t/s | +1 % |
| | Prompt 24k | 630 t/s | 650 t/s | +3 % |
| llama3.3:70b | Gen kurz | 13,6 t/s | 13,4 t/s | −1 % |
| | Prompt 11k | 477 t/s | 446 t/s | −6 % |

Gen 24k ist nur ein Einzelwert und schwankt bei den MTP-Modellen stark (35B Q4: 79,6 → 107,2 t/s, 27B Q4: 43,2 → 31,8 t/s), daher hier nicht gewertet. Die Ladezeiten hängen vom Dateicache ab.

## Fazit

- **Für die R9700 allein spielt der Slot praktisch keine Rolle.** Generierung gleich, Prompt-Verarbeitung höchstens −2 bis −9 %, Laden sogar etwas schneller. Das Modell liegt komplett im VRAM; über PCIe laufen nur Tokens und Logits.
- **Ladezeit ist nicht PCIe-limitiert.** Etwa 1 GB/s in allen Läufen, weit unter dem, was auch 4.0 x4 (~7 GB/s) schafft.
- **Verteilt auf beide Karten** kostet die x4-Anbindung der R9700 etwa 0 bis 7 %, am meisten bei langen Prompts. Verteilen lohnt sich ohnehin nur für Modelle über 32 GB (35B Q8, 70B).
- **Die RX 7800 XT profitiert vom ersten Slot** (+9 % Generierung, +20 % Prompt mit 9B), was für den Split-Betrieb mit dem Scout ein kleiner Gewinn ist.
- Die neue Belegung (R9700 Slot 2, RX 7800 XT Slot 1) ist damit insgesamt mindestens gleichwertig.
