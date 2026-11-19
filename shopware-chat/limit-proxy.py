"""Kleiner Proxy vor mcpo (Shopware-MCP).

1. Zusätzliches Tool `shopware_search`: direkte, nur lesende Suche über die Shopware Admin API
   (POST /api/search/<entity>) mit vollen DAL-Kriterien: range-Filter, multi/or, Assoziationen,
   includes, limit, Sortierung, Aggregationen. Das admin-mcp-Paket kann z.B. nicht nach Datum filtern,
   dann öffnet das Modell jede Bestellung einzeln. Mit shopware_search reicht eine Abfrage.
2. Tool-Antworten werden kompakt gemacht (JSON ohne Einrückung, leere Felder weg).
   Ist eine Antwort danach größer als MAX_TOOL_RESULT_CHARS, bekommt das Modell einen Fehler
   statt Teil-Daten und muss die Abfrage eingrenzen. Nur bei Terms-Aggregationen, die sonst zu groß
   wären, werden Einträge mit count 1 als Anzahl zusammengefasst (mit Hinweis).

Lauscht auf 0.0.0.0:8000, mcpo läuft im selben Container auf 127.0.0.1:8001.
"""
import hmac
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("UPSTREAM", "http://127.0.0.1:8001")
MAX_CHARS = int(os.environ.get("MAX_TOOL_RESULT_CHARS", "100000"))
API_KEY = os.environ.get("MCPO_KEY", "")
SW_URL = os.environ.get("SHOPWARE_API_URL", "").rstrip("/")
SW_ID = os.environ.get("SHOPWARE_API_CLIENT_ID", "")
SW_SECRET = os.environ.get("SHOPWARE_API_CLIENT_SECRET", "")
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "host"}

SEARCH_DESCRIPTION = (
    "Schnelle, nur lesende Suche in Shopware mit einer einzigen Abfrage (Admin API /api/search/<entity>). "
    "Bevorzugt verwenden für Listen, Filter nach Datum, Produktnamen, Status, Kunden usw. "
    "criteria ist ein Shopware-DAL-Criteria-Objekt, z.B. für 'Bestellnummern mit Nusstorte der letzten 30 Tage': "
    '{"limit":100,"filter":[{"type":"range","field":"orderDateTime","parameters":{"gte":"2026-10-19T00:00:00"}},'
    '{"type":"contains","field":"lineItems.label","value":"Nusstorte"}],'
    '"includes":{"order":["orderNumber","orderDateTime","amountTotal"]},"sort":[{"field":"orderDateTime","order":"DESC"}]}. '
    "Filtertypen: equals, equalsAny (value als Liste), contains, prefix, suffix, range (parameters gte/lte/gt/lt), "
    "not (queries), multi (operator AND/OR, queries). Felder über Assoziationen mit Punkt: lineItems.label, "
    "orderCustomer.email, stateMachineState.technicalName, deliveries.stateMachineState.technicalName. "
    "Immer 'includes' setzen, damit nur die nötigen Felder geladen werden, und ein passendes limit. "
    "Für Zählungen limit 1 und total-count-mode 1 nutzen oder 'aggregations' "
    '(z.B. {"name":"umsatz","type":"sum","field":"amountTotal"} oder {"name":"pro_kunde","type":"terms","field":"orderCustomer.email","limit":20,"sort":{"field":"_count","order":"DESC"}}). '
    "Entities: order, order_line_item, product, customer, category, sales_channel, ..."
)

_token = {"value": None, "exp": 0.0}
_lock = threading.Lock()


def sw_token() -> str:
    with _lock:
        if _token["value"] and time.time() < _token["exp"] - 30:
            return _token["value"]
        body = json.dumps({"grant_type": "client_credentials", "client_id": SW_ID, "client_secret": SW_SECRET}).encode()
        req = urllib.request.Request(SW_URL + "/api/oauth/token", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        _token["value"], _token["exp"] = d["access_token"], time.time() + int(d.get("expires_in", 600))
        return _token["value"]


def shopware_search(entity: str, criteria: dict) -> tuple[int, bytes]:
    if not re.fullmatch(r"[a-z_]+", entity or ""):
        return 400, json.dumps({"error": "ungueltige entity"}).encode()
    criteria = dict(criteria or {})
    criteria.setdefault("limit", 25)
    criteria.setdefault("total-count-mode", 1)
    req = urllib.request.Request(
        f"{SW_URL}/api/search/{entity.replace('_', '-')}",
        data=json.dumps(criteria).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + sw_token()},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        return 200, json.dumps({"error": f"Shopware {e.code}", "details": e.read().decode("utf-8", "replace")[:2000]}).encode()
    out = {"total": d.get("total"), "data": d.get("data"), "aggregations": d.get("aggregations") or None}
    return 200, json.dumps(out, ensure_ascii=False).encode()


def strip_empty(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v = strip_empty(v)
            if v is None or v == {} or v == [] or k in ("extensions", "apiAlias"):
                continue
            out[k] = v
        return out
    if isinstance(obj, list):
        return [strip_empty(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 200 and obj.lstrip()[:1] in "{[":
        # mcpo gibt die MCP-Antwort oft als JSON-String zurück
        try:
            return strip_empty(json.loads(obj))
        except ValueError:
            return obj
    return obj


def summarize_ones(obj):
    """Nur für zu große Terms-Aggregationen: Einträge mit count 1 als Anzahl zusammenfassen."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "buckets" and isinstance(v, list) and v and all(isinstance(b, dict) and "count" in b for b in v):
                v = sorted(v, key=lambda b: b.get("count") or 0, reverse=True)
                ones = [b for b in v if (b.get("count") or 0) <= 1]
                out[k] = {
                    "anzahl_buckets_gesamt": len(v),
                    "summe_count_gesamt": sum(b.get("count") or 0 for b in v),
                    "buckets_count_groesser_1": [b for b in v if (b.get("count") or 0) > 1],
                    "buckets_count_1": {"anzahl": len(ones), "hinweis": "zu viele, einzeln weggelassen, jeweils count 1"},
                }
            else:
                out[k] = summarize_ones(v)
        return out
    if isinstance(obj, list):
        return [summarize_ones(v) for v in obj]
    return obj


def dumps(o) -> bytes:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode()


def compact(body: bytes) -> bytes:
    try:
        data = strip_empty(json.loads(body))
    except ValueError:
        return body
    out = dumps(data)
    if len(out) > MAX_CHARS and '"buckets"' in out.decode("utf-8", "replace"):
        out = dumps(summarize_ones(data))
    if len(out) > MAX_CHARS:
        return dumps({
            "error": "ergebnis_zu_gross",
            "zeichen": len(out),
            "hinweis": "Das Ergebnis ist zu groß für den Chat und wurde NICHT geliefert. Mit shopware_search, "
                       "engeren Filtern, includes und kleinerem limit erneut abfragen. Keine Zahlen schätzen.",
        })
    return out


def patch_openapi(body: bytes) -> bytes:
    spec = json.loads(body)
    spec.setdefault("paths", {})["/shopware_search"] = {
        "post": {
            "operationId": "shopware_search",
            "summary": "Shopware Suche (eine Abfrage, nur lesend)",
            "description": SEARCH_DESCRIPTION,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object",
                "required": ["entity", "criteria"],
                "properties": {
                    "entity": {"type": "string", "description": "z.B. order, order_line_item, product, customer"},
                    "criteria": {"type": "object", "description": "Shopware DAL Criteria (filter, includes, limit, sort, aggregations, associations)", "additionalProperties": True},
                },
            }}}},
            "responses": {"200": {"description": "Ergebnis"}},
        }
    }
    return json.dumps(spec).encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers.items() if headers is not None and hasattr(headers, "items") else []):
            if k.lower() not in HOP:
                self.send_header(k, v)
        if not headers:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length) if length else None
        path = self.path.split("?")[0]

        if path == "/shopware_search" and self.command == "POST":
            auth = self.headers.get("Authorization", "")
            if not hmac.compare_digest(auth, "Bearer " + API_KEY):
                return self._send(401, b'{"detail":"unauthorized"}')
            try:
                req = json.loads(data or b"{}")
                status, body = shopware_search(req.get("entity", ""), req.get("criteria") or {})
            except Exception as e:
                status, body = 200, dumps({"error": f"Suche fehlgeschlagen: {e}"})
            before = len(body)
            body = compact(body)
            print(f"POST /shopware_search {req.get('entity') if isinstance(req, dict) else ''} {before} -> {len(body)} bytes", flush=True)
            return self._send(status, body)

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        upstream = urllib.request.Request(UPSTREAM + self.path, data=data, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(upstream, timeout=300) as r:
                status, rheaders, body = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, rheaders, body = e.code, e.headers, e.read()
        except Exception as e:  # mcpo noch nicht bereit o.ä.
            status, rheaders, body = 502, None, dumps({"detail": f"upstream: {e}"})
        before = len(body)
        if path == "/openapi.json" and status == 200:
            body = patch_openapi(body)
        elif self.command == "POST" and status == 200:
            body = compact(body)
            print(f"POST {path} {before} -> {len(body)} bytes", flush=True)
        self._send(status, body, rheaders)

    do_GET = do_POST = _forward

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
