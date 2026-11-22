"""Einrichtung nach dem Start von Open WebUI (Dienst "setup"). Spielt config.json ein:
Ollama-Verbindungen, Websuche, Tool-Server, Task-Modell, Standardmodell/Reihenfolge, Favoriten des Admins,
Namen/Beschreibungen der Basismodelle, eigene Workspace-Modelle (Tools und Websuche standardmässig an) und PDF-Einstellungen.
${NAME} in config.json wird durch die Umgebungsvariable NAME (aus .env) ersetzt."""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ["WEBUI_INTERNAL_URL"].rstrip("/")


def call(path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]


def env(value):
    """${NAME} rekursiv durch Umgebungsvariablen ersetzen."""
    if isinstance(value, dict):
        return {k: env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [env(v) for v in value]
    if isinstance(value, str):
        def repl(m):
            if m.group(1) not in os.environ:
                sys.exit(f"Umgebungsvariable {m.group(1)} fehlt (.env)")
            return os.environ[m.group(1)]
        return re.sub(r"\$\{(\w+)\}", repl, value)
    return value


def report(what, status, res=None):
    print(f"{what}: {'ok' if status == 200 else f'Fehler {status} {res}'}")


for _ in range(100):
    try:
        if call("/health")[0] == 200:
            break
    except Exception:
        pass
    time.sleep(3)
else:
    sys.exit("Open WebUI nicht erreichbar")

# Anmeldung: ADMIN_TOKEN (API-Key eines Admins) oder E-Mail + Passwort
token = os.environ.get("ADMIN_TOKEN")
if not token:
    status, res = call("/api/v1/auths/signin", {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    if status != 200:
        sys.exit(f"Admin-Login fehlgeschlagen: {status} (WEBUI_ADMIN_PASSWORD in .env aktuell? Sonst WEBUI_ADMIN_TOKEN setzen)")
    token = res["token"]

cfg = env(json.load(open("/config.json", encoding="utf-8")))
ALL = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]

# 1. Ollama-Verbindungen
o = cfg["ollama"]
report("Ollama", *call("/ollama/config/update",
                       {"ENABLE_OLLAMA_API": True, "OLLAMA_BASE_URLS": o["urls"], "OLLAMA_API_CONFIGS": o["verbindungen"]}, token))

# 2. Websuche (nur die angegebenen Felder, Rest bleibt)
report("Websuche", *call("/api/v1/retrieval/config/update", {"web": cfg["websuche"]}, token))

# 2b. PDF-Auslese (OCR für Scans)
report("Dokumente", *call("/api/v1/retrieval/config/update",
                          {k: v for k, v in cfg["dokumente"].items() if not k.startswith("_")}, token))

# 3. Tool-Server
report("Tool-Server", *call("/api/v1/configs/tool_servers", {"TOOL_SERVER_CONNECTIONS": cfg["tool_server"]}, token))

# 4. Task-Modell (Titel, Tags, Folgefragen, Suchanfragen) für lokale und externe Modelle
status, tasks = call("/api/v1/tasks/config", token=token)
if status == 200:
    tasks["TASK_MODEL"] = tasks["TASK_MODEL_EXTERNAL"] = cfg["task_modell"]
    status, tasks = call("/api/v1/tasks/config/update", tasks, token)
report(f"Task-Modell {cfg['task_modell']}", status, tasks)


# 5. Modelle
def upsert(model):
    status, res = call("/api/v1/models/create", model, token)
    if status != 200:
        status, res = call(f"/api/v1/models/model/update?id={model['id']}", model, token)
    report(f"Modell {model['id']}", status, res)


# Basismodelle: nur Name/Beschreibung (und optional Tools/Fähigkeiten) setzen, übrige Felder behalten
for model_id, m in cfg["basismodelle"].items():
    status, existing = call(f"/api/v1/models/model?id={model_id}", token=token)
    existing = existing if status == 200 and isinstance(existing, dict) else {}
    meta = {**(existing.get("meta") or {}), **{k: v for k, v in m.items() if k != "name"}}
    upsert({"id": model_id, "base_model_id": None, "name": m.get("name") or existing.get("name") or model_id,
            "meta": meta, "params": existing.get("params") or {},
            "access_grants": existing.get("access_grants") or ALL, "is_active": True})

# Eigene Workspace-Modelle
for m in cfg["modelle"]:
    params = {"function_calling": "native", **m.get("params", {})}
    if m.get("system"):
        params["system"] = m["system"]
    upsert({
        "id": m["id"],
        "base_model_id": m["basis"],
        "name": m["name"],
        "meta": {
            "description": f"{m['description']} ({m['basis']})",
            "toolIds": m.get("tools", []),
            "defaultFeatureIds": m.get("features", []),
            "capabilities": m.get("capabilities") or {"file_upload": True, "web_search": True, "citations": True,
                                                      "status_updates": True, "builtin_tools": True},
        },
        "params": params,
        "access_grants": ALL,
        "is_active": True,
    })

# 6. Standardmodell und Reihenfolge (übrige Werte unverändert lassen)
status, current = call("/api/v1/configs/models", token=token)
if status == 200:
    current["DEFAULT_MODELS"] = cfg["standardmodell"]
    current["MODEL_ORDER_LIST"] = cfg["modell_reihenfolge"]
    status, current = call("/api/v1/configs/models", current, token)
report(f"Standardmodell {cfg['standardmodell']}", status, current)

# 7. Favoriten (angepinnte Modelle) des Admin-Benutzers
status, settings = call("/api/v1/users/user/settings", token=token)
if status == 200:
    settings = settings or {}
    settings.setdefault("ui", {})["pinnedModels"] = cfg["favoriten"]
    status, settings = call("/api/v1/users/user/settings/update", settings, token)
report("Favoriten", status, settings)
