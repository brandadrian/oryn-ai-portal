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
