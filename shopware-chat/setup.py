"""Einmalige Einrichtung nach dem Start von Open WebUI (läuft im Dienst "setup").

1. Standardmodell als Workspace-Modell anlegen bzw. aktualisieren: Systemprompt, Shopware-Tool, für alle sichtbar.
   (Der globale Systemprompt aus DEFAULT_MODEL_PARAMS greift bei Basismodellen ohne Eintrag nicht.)
2. Skills aus skills/<id>/SKILL.md anlegen bzw. aktualisieren (für alle Benutzer).
3. Optional den einfachen Benutzer anlegen (CHAT_USER_EMAIL), falls es ihn noch nicht gibt.
"""
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

# 1. Modell
model_id = os.environ["MODEL_ID"]
model = {
    "id": model_id,
    "base_model_id": None,
    "name": os.environ.get("MODEL_NAME") or model_id,
    "meta": {"toolIds": ["server:shopware"], "description": "Shopware-Assistent", "capabilities": {}},
    "params": {"system": os.environ.get("SYSTEM_PROMPT", ""), "function_calling": "native"},
    "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
    "is_active": True,
}
status, res = call("/api/v1/models/create", model, token)
if status != 200:
    status, res = call(f"/api/v1/models/model/update?id={model_id}", model, token)
print(f"Modell {model_id}: {'ok' if status == 200 else f'Fehler {status} {res}'}")

# 2. Skills aus /skills/<id>/SKILL.md (Frontmatter mit name und description), für alle Benutzer
SKILLS_DIR = "/skills"
if os.path.isdir(SKILLS_DIR):
    for skill_id in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, skill_id, "SKILL.md")
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        meta, body = {}, text
        if text.startswith("---"):
            _, front, body = text.split("---", 2)
            for line in front.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        skill = {
            "id": skill_id,
            "name": meta.get("name") or skill_id,
            "description": meta.get("description", ""),
            "content": text,
            "meta": {"tags": ["shopware"]},
            "is_active": True,
            "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
        }
        exists = call(f"/api/v1/skills/id/{skill_id}", token=token)[0] == 200
        status, res = call(f"/api/v1/skills/id/{skill_id}/update" if exists else "/api/v1/skills/create", skill, token)
        print(f"Skill {skill_id}: {('aktualisiert' if exists else 'angelegt') if status == 200 else f'Fehler {status} {res}'}")

# 3. Einfacher Benutzer
email = os.environ.get("USER_EMAIL", "")
if email:
    status, res = call("/api/v1/auths/add", {
        "name": os.environ.get("USER_NAME") or "Benutzer",
        "email": email,
        "password": os.environ.get("USER_PASSWORD", ""),
        "role": "user",
    }, token)
    print(f"Benutzer {email}: " + ("angelegt" if status == 200 else f"nicht angelegt (existiert evtl. schon): {res}"))
