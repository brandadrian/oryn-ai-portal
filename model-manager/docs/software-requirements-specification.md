# Software Requirements Specification

## Scope

Web UI to list Ollama models and load or unload them. No pulling, creating or deleting of models.

## Stakeholders

- Adrian (owner, only user)

## Use cases

- **UC-1 Load model:** the admin opens the UI, picks a model and clicks "Laden"; the previously loaded model is evicted.
- **UC-2 Unload model:** the admin clicks "Entladen" to free the VRAM.
- **UC-3 Check status:** the admin sees which model is loaded, its VRAM size and when it expires.
- **UC-4 Restart Ollama:** the admin restarts Ollama to free VRAM and RAM completely.

## Functional requirements

| ID | Weight | Requirement |
| --- | --- | --- |
| FR-1 | Shall | List all models defined in `models/*.Modelfile` with name and purpose ("WOFÜR"). |
| FR-2 | Shall | Mark each model as installed / not installed and loaded / not loaded. |
| FR-3 | Shall | Load a model via `/api/generate` with the configured `keep_alive`. |
| FR-4 | Shall | Unload a model via `/api/generate` with `keep_alive: 0`. |
| FR-5 | Should | List installed models without a Modelfile separately. |
| FR-6 | Should | Show Ollama errors (e.g. model not found) next to the model. |
| FR-7 | Should | Refresh the status automatically (every 5 s). |
| FR-8 | Should | Show how much of the loaded model runs on the GPU. |
| FR-9 | Should | Restart the native Ollama on request (host agent), after a confirmation. |

## Non-functional requirements

| ID | Weight | Requirement |
| --- | --- | --- |
| NFR-1 | Shall | UI and API require a login (HTTP Basic Auth, one user from `.env`). |
| NFR-2 | Shall | Credentials are not committed and not logged. |
| NFR-3 | Shall | Runs as a Docker container behind the existing Traefik (network `proxy`). |
| NFR-4 | Should | Starts automatically with `scripts/start-all.ps1`. |

## Assumptions

- Ollama runs natively on Windows on port 11434 with `OLLAMA_MAX_LOADED_MODELS=1`.
- The first non-separator comment line of a Modelfile is the Ollama model name.

## Open issues

- Second Ollama instance (port 11435, split mode) is not supported.
