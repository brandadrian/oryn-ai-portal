"""Nur lesender Datei-MCP für den Maxcluster-Server (SFTP-User mit "Nur lesender Zugriff").

Tools: ordner_auflisten, dateien_suchen, datei_lesen, inhalt_suchen.
Es werden ausschliesslich SFTP-Lesebefehle verwendet (listdir_attr, stat, open "r").
Der SFTP-User hat keine Shell, darum wird für die Inhaltssuche jede Datei gelesen
(begrenzt über Dateianzahl, Dateigrösse und Zeit).
"""
import fnmatch
import os
import posixpath
import re
import stat
import threading
import time
from contextlib import contextmanager

import paramiko
from mcp.server.fastmcp import FastMCP

HOST = os.environ["SSH_HOST"]
USER = os.environ["SSH_USER"]
PORT = int(os.environ.get("SSH_PORT", "22"))
KEY_FILE = os.environ.get("SSH_KEY_FILE", "/keys/id_key")
KNOWN_HOSTS = os.environ.get("SSH_KNOWN_HOSTS", "/keys/known_hosts")

MAX_RESULTS = int(os.environ.get("FILES_MAX_RESULTS", "150"))
MAX_READ_BYTES = int(os.environ.get("FILES_MAX_READ_BYTES", "60000"))
MAX_SCAN_FILES = int(os.environ.get("FILES_MAX_SCAN_FILES", "400"))
MAX_SCAN_FILE_BYTES = int(os.environ.get("FILES_MAX_SCAN_FILE_BYTES", "2000000"))
TIME_BUDGET_S = float(os.environ.get("FILES_TIME_BUDGET_S", "60"))
# Ordner, die beim Durchsuchen standardmässig übersprungen werden (gross und selten gesucht)
DEFAULT_SKIP = [s for s in os.environ.get(
    "FILES_SKIP_DIRS",
    ".cache,.npm,.nvm,.npm-packages,.vscode-server,.vscode-remote-containers,.dotnet,.composer,node_modules,vendor,"
    "var/cache,public/thumbnail,public/media,files/media,backups,db_backup,restore,releases,.dep,htdocs,journal,atop,sysstat",
).split(",") if s]

# Optional: nur diese Ordner (relativ zum Arbeitsordner) sind erlaubt, z. B. "shopware.geschenkkoerbe.ch,logs".
# Trennt PROD und STAGING: jede Instanz sieht nur ihre eigenen Ordner.
ALLOWED_ROOTS = [r.strip().strip("/") for r in os.environ.get("FILES_ALLOWED_ROOTS", "").split(",") if r.strip()]

_lock = threading.Lock()
_client: paramiko.SSHClient | None = None
_sftp: paramiko.SFTPClient | None = None


def _connect() -> paramiko.SFTPClient:
    global _client, _sftp
    client = paramiko.SSHClient()
    client.load_host_keys(KNOWN_HOSTS)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())  # nur bekannte Host-Keys
    pkey = None
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            pkey = cls.from_private_key_file(KEY_FILE)
            break
        except Exception:
            continue
    client.connect(HOST, port=PORT, username=USER, pkey=pkey, look_for_keys=False, allow_agent=False, timeout=15)
    _client, _sftp = client, client.open_sftp()
    return _sftp


@contextmanager
def sftp():
    """Eine gemeinsame Verbindung, bei Fehler einmal neu verbinden."""
    with _lock:
        global _sftp
        s = _sftp
        if s is None or s.get_channel() is None or s.get_channel().closed:
            s = _connect()
        try:
            yield s
        except (OSError, paramiko.SSHException, EOFError) as e:
            if isinstance(e, FileNotFoundError) or isinstance(e, PermissionError):
                raise
            _sftp = None
            raise


def _norm(path: str) -> str:
    p = posixpath.normpath("/" + (path or "").strip().lstrip("/"))
    p = "." if p == "/" else p.lstrip("/")
    if ALLOWED_ROOTS and p != "." and not any(p == r or p.startswith(r + "/") for r in ALLOWED_ROOTS):
        raise PermissionError(f"Pfad '{p}' ist hier nicht erlaubt. Erlaubt: {', '.join(ALLOWED_ROOTS)}")
    return p


def _skip(rel: str, include_skipped: bool) -> bool:
    if include_skipped:
        return False
    return any(rel == d or rel.endswith("/" + d) or ("/" + d + "/") in ("/" + rel + "/") for d in DEFAULT_SKIP)


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _fmt_time(t) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t or 0))


def _walk(s: paramiko.SFTPClient, root: str, max_depth: int, include_skipped: bool, deadline: float):
    """Liefert (relpfad, attr) für Dateien, breitensuchend, mit Tiefen- und Zeitlimit."""
    queue = [(r, 1) for r in ALLOWED_ROOTS] if (root == "." and ALLOWED_ROOTS) else [(root, 0)]
    while queue:
        if time.monotonic() > deadline:
            return
        d, depth = queue.pop(0)
        try:
            entries = s.listdir_attr(d)
        except (PermissionError, FileNotFoundError, OSError):
            continue
        for a in sorted(entries, key=lambda x: x.filename):
            rel = a.filename if d == "." else f"{d}/{a.filename}"
            if stat.S_ISDIR(a.st_mode or 0):
                if depth < max_depth and not _skip(rel, include_skipped):
                    queue.append((rel, depth + 1))
            elif stat.S_ISREG(a.st_mode or 0):
                yield rel, a


mcp = FastMCP("maxcluster-files-readonly", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def ordner_auflisten(pfad: str = "") -> str:
    """Listet Ordner und Dateien in einem Ordner auf dem Maxcluster-Server (nur lesend).

    pfad: relativ zum SFTP-Arbeitsordner, z. B. "" (Wurzel), "logs", "shopware.geschenkkoerbe.ch/deployer".
    """
    p = _norm(pfad)
    if p == "." and ALLOWED_ROOTS:
        return "Erlaubte Ordner:\n" + "\n".join(r + "/" for r in ALLOWED_ROOTS)
    with sftp() as s:
        entries = s.listdir_attr(p)
    dirs = sorted(e.filename + "/" for e in entries if stat.S_ISDIR(e.st_mode or 0))
    files = sorted((e for e in entries if not stat.S_ISDIR(e.st_mode or 0)), key=lambda e: e.filename)
    lines = [f"Ordner: /{'' if p == '.' else p}", f"{len(dirs)} Ordner, {len(files)} Dateien", ""]
    lines += dirs
    lines += [f"{e.filename}  ({_fmt_size(e.st_size or 0)}, {_fmt_time(e.st_mtime)})" for e in files[:MAX_RESULTS]]
    if len(files) > MAX_RESULTS:
        lines.append(f"... {len(files) - MAX_RESULTS} weitere Dateien nicht angezeigt")
    return "\n".join(lines)


@mcp.tool()
def dateien_suchen(muster: str, ordner: str = "", max_tiefe: int = 8, auch_grosse_ordner: bool = False) -> str:
    """Sucht Dateien nach Namen (Platzhalter * und ?, gross/klein egal), z. B. "*.log", "promtail*", "*config*.yml".

    ordner: Startordner relativ zum Arbeitsordner (leer = alles).
    auch_grosse_ordner: true durchsucht auch vendor, node_modules, Caches, Media und Backups (langsam).
    Ergebnis: Pfad, Grösse und Änderungsdatum, neueste zuerst.
    """
    root = _norm(ordner)
    pat = muster.strip().lower() or "*"
    hits = []
    deadline = time.monotonic() + TIME_BUDGET_S
    with sftp() as s:
        for rel, a in _walk(s, root, max(0, min(max_tiefe, 20)), auch_grosse_ordner, deadline):
            if fnmatch.fnmatch(posixpath.basename(rel).lower(), pat) or fnmatch.fnmatch(rel.lower(), pat):
                hits.append((rel, a))
                if len(hits) >= MAX_RESULTS:
                    break
    timed_out = time.monotonic() > deadline
    hits.sort(key=lambda h: h[1].st_mtime or 0, reverse=True)
    out = [f"{len(hits)} Treffer für '{muster}' unter /{'' if root == '.' else root}"
           + (" (Limit erreicht)" if len(hits) >= MAX_RESULTS else "")
           + (" (Zeitlimit erreicht, Suche unvollständig)" if timed_out else "")]
    out += [f"/{rel}  ({_fmt_size(a.st_size or 0)}, {_fmt_time(a.st_mtime)})" for rel, a in hits]
    return "\n".join(out)


@mcp.tool()
def datei_lesen(pfad: str, ab_zeile: int = 1, anzahl_zeilen: int = 300) -> str:
    """Liest eine Textdatei vom Server (nur lesend). Bei grossen Dateien einen Ausschnitt wählen.

    ab_zeile: erste Zeile (1 = Anfang, negative Zahl = so viele Zeilen vor dem Ende, z. B. -100 für das Ende eines Logs).
    anzahl_zeilen: maximal so viele Zeilen (höchstens 2000).
    """
    p = _norm(pfad)
    anzahl_zeilen = max(1, min(anzahl_zeilen, 2000))
    with sftp() as s:
        a = s.stat(p)
        if stat.S_ISDIR(a.st_mode or 0):
            return f"/{p} ist ein Ordner. Nutze ordner_auflisten."
        size = a.st_size or 0
        with s.open(p, "r") as f:
            if ab_zeile < 0 and size > MAX_READ_BYTES:
                f.seek(size - MAX_READ_BYTES)  # Ende der Datei
            data = f.read(MAX_READ_BYTES)
    if b"\x00" in data[:4096]:
        return f"/{p} ist eine Binärdatei ({_fmt_size(size)}), Inhalt wird nicht angezeigt."
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    partial = size > len(data)
    if ab_zeile < 0:
        if partial:
            lines = lines[1:]  # erste, evtl. angeschnittene Zeile weglassen
        sel = lines[ab_zeile:][:anzahl_zeilen]
        head = f"/{p} ({_fmt_size(size)}), letzte {len(sel)} Zeilen"
    else:
        start = max(1, ab_zeile)
        sel = lines[start - 1:start - 1 + anzahl_zeilen]
        head = f"/{p} ({_fmt_size(size)}), Zeilen {start}-{start + len(sel) - 1}"
        if partial:
            head += f" (nur die ersten {_fmt_size(MAX_READ_BYTES)} gelesen; für das Ende ab_zeile negativ setzen)"
    return head + "\n\n" + "\n".join(sel)


@mcp.tool()
def inhalt_suchen(text: str, ordner: str, dateimuster: str = "*", regex: bool = False, max_tiefe: int = 8,
                  auch_grosse_ordner: bool = False) -> str:
    """Sucht Text in den Dateien eines Ordners (wie grep, gross/klein egal), z. B. text="CRIF", ordner="shopware.geschenkkoerbe.ch/deployer/current/custom/plugins", dateimuster="*.php".

    Jede Datei wird über SFTP gelesen, deshalb einen möglichst engen Ordner und ein Dateimuster angeben.
    Limits: höchstens 400 Dateien, 2 MB pro Datei, 60 s. Ergebnis: Pfad:Zeile: Inhalt.
    """
    root = _norm(ordner)
    if root == ".":
        return "Bitte einen Ordner angeben. Die ganze Wurzel zu durchsuchen ist zu langsam."
    try:
        rx = re.compile(text if regex else re.escape(text), re.IGNORECASE)
    except re.error as e:
        return f"Ungültiger regulärer Ausdruck: {e}"
    pat = dateimuster.strip().lower() or "*"
    deadline = time.monotonic() + TIME_BUDGET_S
    hits, scanned, skipped_big, files_with_hits = [], 0, 0, 0
    with sftp() as s:
        for rel, a in _walk(s, root, max(0, min(max_tiefe, 20)), auch_grosse_ordner, deadline):
            if not fnmatch.fnmatch(posixpath.basename(rel).lower(), pat):
                continue
            if (a.st_size or 0) > MAX_SCAN_FILE_BYTES:
                skipped_big += 1
                continue
            if scanned >= MAX_SCAN_FILES or time.monotonic() > deadline:
                break
            scanned += 1
            try:
                with s.open(rel, "r") as f:
                    data = f.read(MAX_SCAN_FILE_BYTES)
            except (PermissionError, OSError):
                continue
            if b"\x00" in data[:4096]:
                continue
            found = False
            for i, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    found = True
                    hits.append(f"/{rel}:{i}: {line.strip()[:300]}")
                    if len(hits) >= MAX_RESULTS:
                        break
            files_with_hits += found
            if len(hits) >= MAX_RESULTS:
                break
    notes = []
    if scanned >= MAX_SCAN_FILES:
        notes.append(f"Dateilimit ({MAX_SCAN_FILES}) erreicht")
    if time.monotonic() > deadline:
        notes.append("Zeitlimit erreicht")
    if skipped_big:
        notes.append(f"{skipped_big} Dateien über {_fmt_size(MAX_SCAN_FILE_BYTES)} übersprungen")
    if len(hits) >= MAX_RESULTS:
        notes.append(f"Trefferlimit ({MAX_RESULTS}) erreicht")
    head = (f"{len(hits)} Treffer in {files_with_hits} von {scanned} durchsuchten Dateien unter /{root}"
            + (f" ({'; '.join(notes)}, Suche unvollständig)" if notes else ""))
    return head + ("\n\n" + "\n".join(hits) if hits else "")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
