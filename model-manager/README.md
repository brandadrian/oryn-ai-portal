# Model Manager

Small web UI to load and unload Ollama models. It lists the models defined in
`../models/*.Modelfile` (name and "WOFÜR" purpose from the file header), shows which
are installed and which is loaded (`/api/ps`), and offers one button per model.

Status: in use, single admin login (HTTP Basic Auth).

- https://management.oryn.brandadrian.com (via Traefik, Let's Encrypt)
- https://management.localhost (local, self-signed)

## Overview

```text
Browser --HTTPS--> Traefik (oryn-gateway, network "proxy")
        --HTTP-->  model-manager (ASP.NET, Basic Auth, static UI)
        --HTTP-->  Ollama on Windows (host.docker.internal:11434)
```

- **Load:** `POST /api/generate {model, keep_alive: <KeepAlive>}` without prompt.
  With `OLLAMA_MAX_LOADED_MODELS=1` Ollama evicts the currently loaded model.
- **Unload:** same call with `keep_alive: 0`.
- The status line shows how much of the loaded model is in VRAM (`size_vram / size` from `/api/ps`).
- Models that are installed but have no Modelfile are listed in the dropdown group "Weitere".
- **Restart Ollama** (frees VRAM and RAM completely): the container writes `restart.request` into
  `%LOCALAPPDATA%\Oryn\model-manager` (bind mount `/host`). `scripts\ollama-restart-agent.ps1` runs on Windows,
  picks it up within 2 s, calls `ollama-gpu.ps1 -Mode restart` and writes `status.json` for the UI.
  Register the agent once: `scripts\install-ollama-restart-agent.ps1` (logon task "Oryn Ollama Restart-Agent").

## Setup

```powershell
cd model-manager
copy .env.example .env    # set Manager__Password (min. 8 characters)
docker compose up -d --build
```

`scripts\start-all.ps1` starts the stack at logon.

## Development

```powershell
dotnet test src/ModelManager.slnx
$env:Manager__User="admin"; $env:Manager__Password="local-test-pw"
dotnet run --project src/ModelManager.Api
```

## Configuration

Section `Manager` (`appsettings.json`, env `Manager__*`), see `src/ModelManager.Api/appsettings.example.json`.

| Key | Default | Description |
| --- | --- | --- |
| `OllamaUrl` | `http://localhost:11434` | Ollama base URL (container: `http://host.docker.internal:11434`) |
| `ModelsDir` | `../../../models` | Directory with `*.Modelfile` (container: `/models`, mounted read-only) |
| `KeepAlive` | `24h` | `keep_alive` when loading, e.g. `24h` or `-1` (forever) |
| `RestartDir` | – | Directory shared with the restart agent (container: `/host`); empty hides the restart button |
| `User`, `Password` | – | Login, required, from `.env` (not committed) |

## Logging

Console (`docker logs model-manager`), one line per entry: `timestamp;loglevel;message`.
Load/unload write `command=…;id=…;event=start|done|failed;model=…`, restart `command=restart;id=…;event=requested|rejected`.
The agent logs to `%LOCALAPPDATA%\Oryn\ollama-restart-agent.log`. Credentials are never logged.

## Structure

```text
src/
  ModelManager.slnx
  ModelManager.Api/              endpoints, Basic Auth, logging, static UI (wwwroot)
  ModelManager.Core/             models, options, Modelfile reader, ModelService, IOllamaClient
  ModelManager.Adapters.Ollama/  Ollama REST client
tests/ModelManager.Tests/        unit tests (Modelfile parsing, merge)
docs/                            requirements and system description
```

Details: [docs/README.md](docs/README.md)
