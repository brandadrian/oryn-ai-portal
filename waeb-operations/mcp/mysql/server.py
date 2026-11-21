"""Nur lesender MySQL-MCP für die Shopware-Datenbanken auf dem Maxcluster-Server.

Verbindung über den SSH-Tunnel (Dienst "tunnel", Port 3306). Schutz in drei Stufen:
1. Datenbank-User sollte ein reiner Lese-User sein (nur SELECT, SHOW VIEW).
2. Erlaubt sind nur einzelne Anweisungen, die mit SELECT, WITH, SHOW, DESCRIBE/DESC oder EXPLAIN beginnen.
3. Jede Abfrage läuft in einer READ-ONLY-Transaktion mit Zeitlimit und wird danach zurückgerollt.

Umgebungen (production, staging, ...) kommen aus MYSQL_DATABASES, z. B. "production=sw_prod,staging=sw_stage".
"""
import datetime
import decimal
import os
import re

import pymysql
from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("MYSQL_HOST", "waeb-ops-tunnel")
PORT = int(os.environ.get("MYSQL_PORT", "3306"))
USER = os.environ.get("MYSQL_USER", "")
PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
DATABASES = dict(
    (k.strip(), v.strip())
    for k, v in (p.split("=", 1) for p in os.environ.get("MYSQL_DATABASES", "").split(",") if "=" in p)
)
MAX_ROWS = int(os.environ.get("MYSQL_MAX_ROWS", "500"))
TIMEOUT_MS = int(os.environ.get("MYSQL_TIMEOUT_MS", "30000"))
MAX_CELL = int(os.environ.get("MYSQL_MAX_CELL_CHARS", "500"))

ALLOWED = re.compile(r"^\s*(select|with|show|describe|desc|explain)\b", re.IGNORECASE)
# Auch innerhalb erlaubter Anweisungen verboten (z. B. SELECT ... INTO OUTFILE, FOR UPDATE)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|rename|grant|revoke|call|load_file|"
    r"into\s+(out|dump)file|for\s+update|lock\s+in\s+share\s+mode|sleep|benchmark|handler|load\s+data|set\s+)\b",
    re.IGNORECASE,
)


def _strip_comments_and_strings(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"(--|#)[^\n]*", " ", sql)
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`", "''", sql)


def _check(sql: str) -> str | None:
    bare = _strip_comments_and_strings(sql).strip().rstrip(";").strip()
    if ";" in bare:
        return "Nur eine einzelne Anweisung erlaubt."
    if not ALLOWED.match(bare):
        return "Nur lesende Anweisungen erlaubt: SELECT, WITH, SHOW, DESCRIBE, EXPLAIN."
    m = FORBIDDEN.search(bare)
    if m:
        return f"Nicht erlaubt (nur lesen): '{m.group(0)}'."
    return None


def _db(umgebung: str) -> str:
    if not USER:
        raise RuntimeError("MySQL-Zugang fehlt: MYSQL_USER/MYSQL_PASSWORD in der .env von waeb-operations setzen.")
    if len(DATABASES) == 1:
        # Instanz für genau eine Umgebung (Trennung PROD/STAGING): andere Umgebungen gibt es hier nicht
        (only_key, only_db), = DATABASES.items()
        if umgebung and umgebung.strip().lower() not in (only_key, ""):
            raise RuntimeError(f"Diese Verbindung ist nur für '{only_key}'. '{umgebung}' ist hier nicht verfügbar.")
        return only_db
    key = (umgebung or "production").strip().lower()
    if key not in DATABASES:
        raise RuntimeError(f"Unbekannte Umgebung '{umgebung}'. Verfügbar: {', '.join(DATABASES) or '(keine, MYSQL_DATABASES setzen)'}")
    return DATABASES[key]


def _run(umgebung: str, sql: str, args=None, max_rows: int = MAX_ROWS):
    db = _db(umgebung)
    conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, database=db, charset="utf8mb4",
                           connect_timeout=10, read_timeout=TIMEOUT_MS / 1000 + 5, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME={TIMEOUT_MS}")
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute("START TRANSACTION READ ONLY")
            cur.execute(sql, args)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(max_rows + 1)
            conn.rollback()
        return db, cols, rows
    finally:
        conn.close()


def _cell(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return v.hex() if len(v) <= 32 else f"<{len(v)} Bytes>"  # Shopware-IDs sind binary(16) -> hex
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat(sep=" ") if isinstance(v, datetime.datetime) else v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    s = str(v).replace("\n", " ").replace("|", "\\|")
    return s if len(s) <= MAX_CELL else s[:MAX_CELL] + f"… (+{len(s) - MAX_CELL} Zeichen)"


def _table(cols, rows, limit) -> str:
    more = len(rows) > limit
    rows = rows[:limit]
    if not cols:
        return "(keine Spalten)"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(_cell(v) for v in r) + " |" for r in rows]
    out.append(f"\n{len(rows)} Zeilen" + (f" (Limit {limit} erreicht, weitere Zeilen nicht geladen; mit WHERE/LIMIT eingrenzen)" if more else ""))
    return "\n".join(out)


mcp = FastMCP("shopware-mysql-readonly", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def umgebungen() -> str:
    """Zeigt die verfügbaren Shopware-Datenbanken (z. B. production, staging)."""
    if not DATABASES:
        return "Keine Datenbanken konfiguriert (MYSQL_DATABASES)."
    return "\n".join(f"- {k}: Datenbank `{v}`" for k, v in DATABASES.items())


@mcp.tool()
def tabellen_auflisten(umgebung: str = "", filter: str = "") -> str:
    """Listet die Tabellen einer Shopware-Datenbank mit ungefährer Zeilenzahl.

    umgebung: leer lassen (die Verbindung gehört zu genau einer Umgebung). filter: Teil des Tabellennamens, z. B. "order" oder "product".
    """
    db, cols, rows = _run(umgebung,
                          "SELECT table_name AS tabelle, table_rows AS zeilen_ca, "
                          "ROUND((data_length+index_length)/1024/1024,1) AS mb "
                          "FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name LIKE %s "
                          "ORDER BY table_name", (f"%{filter}%",), max_rows=2000)
    return f"Datenbank `{db}` ({umgebung})\n\n" + _table(cols, rows, 2000)


@mcp.tool()
def tabelle_beschreiben(tabelle: str, umgebung: str = "") -> str:
    """Zeigt Spalten, Typen, Schlüssel und Fremdschlüssel einer Tabelle, z. B. "order", "order_line_item", "product".

    Hinweis: Shopware-IDs sind binary(16); in Abfragen mit HEX(id) bzw. UNHEX('...') arbeiten.
    """
    if not re.fullmatch(r"[A-Za-z0-9_]+", tabelle or ""):
        return "Ungültiger Tabellenname."
    db, cols, rows = _run(umgebung,
                          "SELECT column_name AS spalte, column_type AS typ, is_nullable AS null_erlaubt, column_key AS schluessel, "
                          "column_default AS standard FROM information_schema.columns "
                          "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position", (tabelle,), max_rows=1000)
    if not rows:
        return f"Tabelle `{tabelle}` nicht gefunden in `{db}`."
    _, fcols, frows = _run(umgebung,
                           "SELECT column_name AS spalte, referenced_table_name AS verweist_auf, referenced_column_name AS ziel_spalte "
                           "FROM information_schema.key_column_usage WHERE table_schema = DATABASE() AND table_name = %s "
                           "AND referenced_table_name IS NOT NULL", (tabelle,), max_rows=200)
    return (f"Tabelle `{tabelle}` in `{db}` ({umgebung})\n\n" + _table(cols, rows, 1000)
            + ("\n\nFremdschlüssel:\n\n" + _table(fcols, frows, 200) if frows else ""))


@mcp.tool()
def sql_abfrage(sql: str, umgebung: str = "", max_zeilen: int = 100) -> str:
    """Führt eine einzelne lesende SQL-Abfrage aus (SELECT, WITH, SHOW, DESCRIBE, EXPLAIN) und gibt eine Tabelle zurück.

    umgebung: leer lassen (die Verbindung gehört zu genau einer Umgebung). max_zeilen: höchstens 500.
    Tipps für Shopware: IDs mit HEX(id) ausgeben; nur die aktuelle Version mit version_id = UNHEX('0fa91ce3e96a4bc2be4bd9ce752c3425');
    Bestellungen in `order` (Backticks!), Positionen in order_line_item, Kunden in order_customer.
    Immer LIMIT setzen und nur benötigte Spalten abfragen. Zeitlimit 30 s.
    """
    err = _check(sql)
    if err:
        return err
    limit = max(1, min(int(max_zeilen or 100), MAX_ROWS))
    try:
        db, cols, rows = _run(umgebung, sql.strip().rstrip(";"), max_rows=limit)
    except pymysql.err.MySQLError as e:
        return f"MySQL-Fehler: {e.args[-1] if e.args else e}"
    return f"`{db}` ({umgebung})\n\n" + _table(cols, rows, limit)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
