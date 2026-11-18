"""Kleiner Proxy vor mcpo: macht große Tool-Antworten kompakt, ohne Daten zu verfälschen.

Shopware liefert Aggregationen (z.B. dal_aggregate "terms" über alle Kunden) als formatiertes JSON
mit zehntausenden Buckets, mehrere MB. Das sprengt das Kontextfenster des Modells.

Was der Proxy macht (nur bei Tool-Aufrufen, POST):
1. JSON ohne Einrückung ausgeben (spart über die Hälfte, verlustfrei).
2. Terms-Buckets nach Anzahl absteigend sortieren und die vielen Einträge mit count 1 zusammenfassen
   (Anzahl + Summe), alle mit count > 1 bleiben vollständig. Gesamtzahlen bleiben exakt.
3. Ist es danach immer noch zu groß, wird KEIN Teil-Ergebnis geliefert, sondern ein Fehler mit der Bitte,
   die Abfrage einzugrenzen. So rechnet das Modell nie mit unvollständigen Daten.

Lauscht auf 0.0.0.0:8000, mcpo läuft im selben Container auf 127.0.0.1:8001.
"""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("UPSTREAM", "http://127.0.0.1:8001")
MAX_CHARS = int(os.environ.get("MAX_TOOL_RESULT_CHARS", "400000"))
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "host"}


def compact_buckets(buckets: list) -> dict | list:
    if not buckets or not all(isinstance(b, dict) and "count" in b for b in buckets):
        return buckets
    buckets = sorted(buckets, key=lambda b: b.get("count") or 0, reverse=True)
    many = [b for b in buckets if (b.get("count") or 0) > 1]
    ones = [b for b in buckets if (b.get("count") or 0) <= 1]
    if len(ones) < 50:
        return buckets
    return {
        "anzahl_buckets_gesamt": len(buckets),
        "summe_count_gesamt": sum(b.get("count") or 0 for b in buckets),
        "buckets_count_groesser_1": many,
        "buckets_count_1": {"anzahl": len(ones), "hinweis": "einzeln weggelassen, jeweils count 1"},
    }


def walk(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = compact_buckets(walk(v)) if k == "buckets" and isinstance(v, list) else walk(v)
        return out
    if isinstance(obj, list):
        return [walk(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 200 and obj.lstrip()[:1] in "{[":
        # mcpo gibt die MCP-Antwort oft als JSON-String zurück
        try:
            return json.dumps(walk(json.loads(obj)), ensure_ascii=False, separators=(",", ":"))
        except ValueError:
            return obj
    return obj


def compact(body: bytes) -> bytes:
    try:
        data = walk(json.loads(body))
    except ValueError:
        return body
    out = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    if len(out) > MAX_CHARS:
        return json.dumps({
            "error": "ergebnis_zu_gross",
            "zeichen": len(out),
            "hinweis": "Das Ergebnis ist zu groß für den Chat und wurde NICHT geliefert. "
                       "Abfrage eingrenzen (Filter, Zeitraum, Seiten) und erneut versuchen. "
                       "Keine Zahlen schätzen.",
        }, ensure_ascii=False).encode()
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        req = urllib.request.Request(UPSTREAM + self.path, data=data, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                status, rheaders, body = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, rheaders, body = e.code, e.headers, e.read()
        except Exception as e:  # mcpo noch nicht bereit o.ä.
            status, rheaders, body = 502, {}, json.dumps({"detail": f"upstream: {e}"}).encode()
        before = len(body)
        if self.command == "POST" and status == 200:
            body = compact(body)
        self.send_response(status)
        for k, v in (rheaders.items() if hasattr(rheaders, "items") else []):
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"{self.command} {self.path} {status} {before} -> {len(body)} bytes", flush=True)

    do_GET = do_POST = _forward

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
