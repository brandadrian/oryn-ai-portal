"""Einrichtung nach dem Start von Open WebUI (Dienst "setup"):
1. Modelle aus models.json mit Name und Beschreibung anlegen bzw. aktualisieren (Tools an, native Tool-Aufrufe, für alle sichtbar).
2. Skills aus skills/<id>/SKILL.md anlegen bzw. aktualisieren, für alle Benutzer."""
import json
import os
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


for _ in range(100):
    try:
        if call("/health")[0] == 200:
            break
    except Exception:
        pass
    time.sleep(3)
else:
    sys.exit("Open WebUI nicht erreichbar")

status, res = call("/api/v1/auths/signin", {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
if status != 200:
    sys.exit(f"Admin-Login fehlgeschlagen: {status}")
token = res["token"]

# 1. Modelle (models.json): Basismodelle ausblenden, pro Umgebung (PROD/STAGING) eigene Modelle anlegen,
#    die ausschliesslich die Tools ihrer Umgebung haben. So werden Daten nie zwischen den Umgebungen vermischt.
ALL = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def upsert(model):
    status, res = call("/api/v1/models/create", model, token)
    if status != 200:
        status, res = call(f"/api/v1/models/model/update?id={model['id']}", model, token)
    print(f"Modell {model['id']}: {'ok' if status == 200 else f'Fehler {status} {res}'}")


cfg = json.load(open("/models.json", encoding="utf-8"))
for base in cfg["basismodelle"]:
    upsert({"id": base, "base_model_id": None, "name": base,
            "meta": {"hidden": True, "toolIds": [], "description": "Basismodell ohne Tools (ausgeblendet)", "capabilities": {}},
            # Task-Modell (9B): ohne Denkphase, sonst braucht ein Titel 20 s statt unter 1 s
            "params": {"reasoning_effort": "none"} if base == "qwen3.5:9b" else {}, "access_grants": [], "is_active": True})
UMGEBUNG = os.environ.get("UMGEBUNG", "")  # jede Instanz bekommt nur die Modelle ihrer Umgebung
for env_key, env in cfg["umgebungen"].items():
    if UMGEBUNG and env_key != UMGEBUNG:
        continue
    for v in cfg["varianten"]:
        fmt = {"label": env["label"], "shop": env["shop"]}
        upsert({
            "id": f"{env_key}-{v['suffix']}",
            "base_model_id": v["basis"],
            "name": v["name"].format(**fmt),
            "meta": {"description": v["description"].format(**fmt) + f" ({v['basis']})", "toolIds": env["tools"],
                     "tags": [{"name": env["label"]}], "capabilities": {}},
            "params": {"system": cfg["systemprompt"].replace("{regeln}", env["regeln"]), "function_calling": "native"},
            "access_grants": ALL,
            "is_active": True,
        })
    # Agenten: feste Aufgabe, eigene Tools (nur dieser Umgebung), Skills und Systemprompt
    def tool_id(t):
        if t == "metrics":
            return "server:mcp:metrics"
        return f"server:shopware-{env_key}" if t == "shopware" else f"server:mcp:{t}-{env_key}"

    def fill(text):
        for k, v in (("{label}", env["label"]), ("{shop}", env["shop"]), ("{regeln}", env["regeln"]),
                     ("{schreibhinweis}", env.get("schreibhinweis", ""))):
            text = text.replace(k, v)
        return text

    for a in cfg.get("agenten", []):
        upsert({
            "id": f"{env_key}-{a['suffix']}",
            "base_model_id": a["basis"],
            "name": fill(a["name"]),
            "meta": {"description": fill(a["description"]) + f" ({a['basis']})", "toolIds": [tool_id(t) for t in a["tools"]],
                     "skillIds": a.get("skills", []), "tags": [{"name": env["label"]}, {"name": "Agent"}], "capabilities": {}},
            "params": {"system": fill(a["prompt"]), "function_calling": "native"},
            "access_grants": ALL,
            "is_active": True,
        })

# 2. Skills
SKILLS_DIR = "/skills"
for skill_id in sorted(os.listdir(SKILLS_DIR)):
    path = os.path.join(SKILLS_DIR, skill_id, "SKILL.md")
    if not os.path.isfile(path):
        continue
    text = open(path, encoding="utf-8").read()
    meta = {}
    if text.startswith("---"):
        _, front, _ = text.split("---", 2)
        for line in front.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    skill = {
        "id": skill_id,
        "name": meta.get("name") or skill_id,
        "description": meta.get("description", ""),
        "content": text,
        "meta": {"tags": ["waeb-operations"]},
        "is_active": True,
        "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
    }
    exists = call(f"/api/v1/skills/id/{skill_id}", token=token)[0] == 200
    status, res = call(f"/api/v1/skills/id/{skill_id}/update" if exists else "/api/v1/skills/create", skill, token)
    print(f"Skill {skill_id}: {('aktualisiert' if exists else 'angelegt') if status == 200 else f'Fehler {status} {res}'}")
