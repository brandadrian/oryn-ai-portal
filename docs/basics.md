# Basics – Copilot, Modelfiles, Performance

[← zurück zur README](../README.md)

## Instructions, Skills, Agents (Copilot in VS Code)

| | Instructions | Skills | Agents |
|---|---|---|---|
| Datei | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` | `.github/skills/<name>/SKILL.md` | `.github/agents/<name>.agent.md` |
| Wann aktiv | Immer (bzw. per `applyTo` für passende Dateien) | Bei Bedarf: Copilot lädt den Skill, wenn die Beschreibung zur Anfrage passt | Wenn man den Agent im Chat explizit auswählt |
| Wofür | Dauerhafte Regeln: Sprache, Stil, Konventionen | Wiederverwendbare Anleitung für eine bestimmte Aufgabe (Schritte, Skripte, Beispiele) | Eigene Rolle mit eigenem Prompt **und eigener Tool-Liste** |
| Tools | Ändert nichts an den Tools | Ändert nichts an den Tools | Schränkt die Tools ein (`tools:` im Frontmatter) |
| Beispiel Incident-Analyse | „Antworte auf Deutsch mit Ursache, Belege, Lösungsvorschlag.“ | „Incident analysieren: zuerst `search`/`esql` (Index dok-event), dann `loki_query`, dann GitLab.“ | `incident.agent.md` mit nur `search`, `esql`, `loki_query` (+ GitLab) als Tools |

**Empfehlung für den Incident-Use-Case:** einen Agent mit eingeschränkter Tool-Liste anlegen. Die gemessenen Requests hatten 53–68 Tools; jedes Tool landet als Schema im Prompt, macht ihn länger, langsamer und verwirrt das lokale Modell bei der Tool-Wahl.

## Weitere wichtige Punkte

**SYSTEM im Modelfile wird ersetzt.** Der `SYSTEM`-Prompt im Modelfile greift nur, wenn der Client keine eigene System-Nachricht schickt. Copilot schickt immer eine, deshalb zählt dort `.github/copilot-instructions.md` (bzw. der Agent-Prompt), nicht das Modelfile.

**Kontextlänge kommt aus dem Modelfile.** `PARAMETER num_ctx 131072` steht in den `-128k`-Modelfiles und gilt für diese Modelle fest. `OLLAMA_CONTEXT_LENGTH` ist nur der Default für Modelle ohne eigenes `num_ctx`.

**Performance hängt an der Prompt-Länge.** Lokal bremst vor allem die Länge des Prompts, und die wächst mit jedem Tool und dem System-Prompt der Coding-Harness. Für Chat mit Tools daher schlanke Clients nutzen (z. B. Open WebUI mit nativem Tool Calling) statt Copilot/Coding-Harness.

## VRAM-Bedarf eines 27B-Modells

`VRAM ≈ Gewichte + KV-Cache + Overhead`

| Teil | Formel | 27B, Q4_K_M, 128k, KV q8_0 |
|---|---|---|
| Gewichte | Parameter × Bit ÷ 8 (Q4_K_M ≈ 4,8 Bit, Q8_0 ≈ 8,5 Bit) | 27,3 Mrd. × 4,8 ÷ 8 ≈ **16 GB** |
| KV-Cache | 2 (K+V) × Attention-Layer × KV-Heads × Head-Dim × Kontext × Byte (q8_0 ≈ 1, f16 = 2) | dicht, 64 Layer: 2 × 64 × 4 × 256 × 131072 × 1 ≈ **17 GB** |
| Overhead | Compute-Puffer, Ausgabe usw. | ca. 0,5–1,5 GB |

Ein dichtes 27B mit 128k bräuchte also gut 34 GB und passte nicht auf die R9700 (32 GB).

**Echtes Beispiel `qwen3.8:27b-q4-128k`: 100 % GPU auf der R9700.** Das Modell ist ein Hybrid (`ollama show -v`:
`block_count 65`, `full_attention_interval 4`, `ssm.*`). Nur jeder 4. Layer hat echte Attention (16 von 64), die übrigen
48 sind rekurrente Layer mit festem Zustand, der nicht mit dem Kontext wächst. Laut `server.log`:

| Puffer | Größe |
|---|---|
| Gewichte (`Vulkan0 model buffer`) | 15,0 GiB (+ 0,7 GiB Embeddings im RAM) |
| KV-Cache, 16 Layer, q8_0 | 4,25 GiB (2 × 16 × 4 × 256 × 131072 × 1 Byte) |
| Rekurrenter Zustand (`RS buffer`), 48 Layer | 0,73 GiB, unabhängig vom Kontext |
| KV des MTP-Layers (Layer 65, f16) | 0,5 GiB |
| Compute-Puffer | ca. 0,5 GiB |

Zusammen ca. 21 GiB. `ollama ps` zeigt für dasselbe Modell 17 GB, die Werte weichen also ab. Maßgeblich für „passt es?“ ist
`offloaded X/X layers` im `server.log` bzw. „100% GPU“ in `ollama ps`.

Faustregel: Bei Hybrid-Modellen den KV-Cache nur für die Attention-Layer rechnen (hier 64 ÷ 4 = 16; Layer 65 ist der MTP-Layer).
Doppelter Kontext verdoppelt nur diesen Teil. `OLLAMA_NUM_PARALLEL=2` verdoppelt ihn ebenfalls.
