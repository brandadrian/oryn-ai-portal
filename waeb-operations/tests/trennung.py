"""Prüft die Trennung PROD/STAGING der MCP-Server. Läuft im Open-WebUI-Container (internes Netz):
docker cp tests/trennung.py waeb-operations-open-webui-1:/tmp/ && docker exec -e MCPO_PROD_KEY=... -e MCPO_STAGING_KEY=... waeb-operations-open-webui-1 python3 /tmp/trennung.py
"""
import json
import os
import urllib.error
import urllib.request


def mcp(alias, tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(f"http://{alias}:8000/mcp", data=body, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=120).read().decode()
    data = json.loads([l[5:] for l in raw.splitlines() if l.startswith("data:")][-1])
    r = data.get("result") or {}
    return ("FEHLER " if r.get("isError") else "") + (r.get("content") or [{}])[0].get("text", str(data))[:160].replace("\n", " | ")


def oapi(alias, key, path, body=None):
    req = urllib.request.Request(f"http://{alias}:8000{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


checks = [
    ("Loki PROD, job=shopware (erlaubt)", lambda: mcp("waeb-ops-loki-prod", "loki_query_range", {"query": 'count_over_time({job="shopware"}[5m])', "sinceMinutes": 5, "limit": 1})),
    ("Loki PROD, job=shopware_stage (gesperrt)", lambda: mcp("waeb-ops-loki-prod", "loki_query_range", {"query": '{job="shopware_stage"}', "sinceMinutes": 5})),
    ("Loki STAGING, job=shopware (gesperrt)", lambda: mcp("waeb-ops-loki-staging", "loki_query_range", {"query": '{job="shopware"}', "sinceMinutes": 5})),
    ("Loki STAGING, job=~shopware.* (gesperrt)", lambda: mcp("waeb-ops-loki-staging", "loki_query_range", {"query": '{job=~"shopware.*"}', "sinceMinutes": 5})),
    ("Loki STAGING, ohne job (gesperrt)", lambda: mcp("waeb-ops-loki-staging", "loki_query_range", {"query": '{filename=~".+"}', "sinceMinutes": 5})),
    ("Dateien PROD, Wurzel", lambda: mcp("waeb-ops-files-prod", "ordner_auflisten", {"pfad": ""})),
    ("Dateien PROD, Staging-Ordner (gesperrt)", lambda: mcp("waeb-ops-files-prod", "ordner_auflisten", {"pfad": "shopware-staging.geschenkkoerbe.ch"})),
    ("Dateien STAGING, Prod-Ordner (gesperrt)", lambda: mcp("waeb-ops-files-staging", "ordner_auflisten", {"pfad": "shopware.geschenkkoerbe.ch/deployer"})),
    ("Dateien STAGING, ../ Trick (gesperrt)", lambda: mcp("waeb-ops-files-staging", "datei_lesen", {"pfad": "shopware-staging.geschenkkoerbe.ch/../shopware.geschenkkoerbe.ch/deployer/.dep/latest_release"})),
    ("MySQL STAGING, umgebung=production (gesperrt)", lambda: mcp("waeb-ops-mysql-staging", "tabellen_auflisten", {"umgebung": "production"})),
    ("MySQL PROD, umgebungen", lambda: mcp("waeb-ops-mysql-prod", "umgebungen", {})),
]
for name, fn in checks:
    try:
        print(f"{name:48} -> {fn()}")
    except Exception as e:
        print(f"{name:48} -> EXCEPTION {e}")

for env in ("prod", "staging"):
    key = os.environ[f"MCPO_{env.upper()}_KEY"]
    st, body = oapi(f"waeb-ops-shopware-{env}", key, "/openapi.json")
    paths = list(json.loads(body).get("paths", {})) if st == 200 else []
    writes = [p for p in paths if any(w in p for w in ("create", "update", "delete", "upload"))]
    print(f"Shopware {env:8} openapi {st}: {len(paths)} Tools, davon schreibend: {len(writes)} {writes[:3]}")
    st, body = oapi(f"waeb-ops-shopware-{env}", key, "/shopware_search", {"entity": "order", "criteria": {"limit": 1, "includes": {"order": ["orderNumber", "orderDateTime"]}, "sort": [{"field": "orderDateTime", "order": "DESC"}], "total-count-mode": 1}})
    print(f"Shopware {env:8} shopware_search {st}: {body[:160]}")
    if env == "prod":
        st, body = oapi("waeb-ops-shopware-prod", key, "/product_update", {"id": "x"})
        print(f"Shopware prod     product_update (gesperrt) {st}: {body[:120]}")
    st, _ = oapi(f"waeb-ops-shopware-{env}", "falsch", "/shopware_search", {"entity": "order", "criteria": {"limit": 1}})
    print(f"Shopware {env:8} falscher Key -> {st}")
