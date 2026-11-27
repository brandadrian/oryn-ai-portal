# Model Manager – Documentation

Purpose: switch the model Ollama keeps in VRAM from a browser, without a shell on the PC.

```mermaid
flowchart LR
  U[Admin in browser] -->|HTTPS, Basic Auth| T[Traefik]
  T --> M[model-manager]
  M -->|/api/tags, /api/ps, /api/generate| O[Ollama, Windows]
  M -->|read-only| F[(models/*.Modelfile)]
  M -->|restart.request / status.json| A[ollama-restart-agent.ps1, Windows]
  A -->|ollama-gpu.ps1 -Mode restart| O
```

- [Software requirements specification](software-requirements-specification.md)
