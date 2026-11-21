"""Nur lesender Prometheus-MCP für den Maxcluster-Server (node_exporter-Metriken über den SSH-Tunnel).

Ruft ausschliesslich GET-Endpunkte der Prometheus-Query-API auf. Tools:
server_zustand, metriken_auflisten, promql_abfrage, promql_verlauf.
"""
import json
import os
import time
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

PROM = os.environ.get("PROMETHEUS_URL", "http://waeb-ops-tunnel:9090").rstrip("/")
TIMEOUT = float(os.environ.get("PROMETHEUS_TIMEOUT_S", "20"))
MAX_SERIES = int(os.environ.get("PROMETHEUS_MAX_SERIES", "50"))
I = 'instance="localhost:9100"'


def _get(path: str, **params) -> dict:
    url = PROM + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        d = json.load(r)
    if d.get("status") != "success":
        raise RuntimeError(d.get("error") or str(d)[:300])
    return d["data"]


def _labels(m: dict) -> str:
    m = {k: v for k, v in m.items() if k not in ("instance", "job")}
    return "{" + ", ".join(f'{k}="{v}"' for k, v in m.items()) + "}" if m else "{}"


def _num(v: str) -> str:
    try:
        f = float(v)
    except ValueError:
        return v
    return f"{f:.4g}" if abs(f) < 1e6 else f"{f:.4e}"


mcp = FastMCP("maxcluster-metrics-readonly", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def server_zustand() -> str:
    """Kurzer Überblick über den Maxcluster-Server jetzt: CPU, RAM, Disk, Last, Netzwerk, Uptime."""
    q = {
        "CPU belegt (%)": f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle",{I}}}[5m])))',
        "RAM belegt (%)": f'100 * (1 - node_memory_MemAvailable_bytes{{{I}}} / node_memory_MemTotal_bytes{{{I}}})',
        "RAM gesamt (GB)": f'node_memory_MemTotal_bytes{{{I}}} / 1e9',
        "Disk / belegt (%)": f'100 * (1 - node_filesystem_avail_bytes{{mountpoint="/",{I}}} / node_filesystem_size_bytes{{mountpoint="/",{I}}})',
        "Disk / frei (GB)": f'node_filesystem_avail_bytes{{mountpoint="/",{I}}} / 1e9',
        "Load 5 min": f'node_load5{{{I}}}',
        "Kerne": f'count(node_cpu_seconds_total{{mode="idle",{I}}})',
        "Netz eingehend (KB/s)": f'rate(node_network_receive_bytes_total{{device="eth0",{I}}}[5m]) / 1e3',
        "Netz ausgehend (KB/s)": f'rate(node_network_transmit_bytes_total{{device="eth0",{I}}}[5m]) / 1e3',
        "Uptime (Tage)": f'(time() - node_boot_time_seconds{{{I}}}) / 86400',
    }
    out = []
    for name, expr in q.items():
        try:
            res = _get("/api/v1/query", query=expr)["result"]
            out.append(f"- {name}: {_num(res[0]['value'][1]) if res else 'keine Daten'}")
        except Exception as e:
            out.append(f"- {name}: Fehler {e}")
    return "Maxcluster-Server (Prometheus/node_exporter), Stand jetzt:\n" + "\n".join(out)


@mcp.tool()
def metriken_auflisten(filter: str = "") -> str:
    """Listet Metrik-Namen, optional gefiltert, z. B. "memory", "filesystem", "network", "cpu"."""
    names = _get("/api/v1/label/__name__/values")
    hits = [n for n in names if filter.lower() in n.lower()]
    return f"{len(hits)} Metriken" + (f" mit '{filter}'" if filter else "") + ":\n" + "\n".join(hits[:300]) + (
        "\n… (gekürzt, Filter verwenden)" if len(hits) > 300 else "")


@mcp.tool()
def promql_abfrage(promql: str) -> str:
    """Wertet einen PromQL-Ausdruck für jetzt aus (instant), z. B.
    100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)."""
    data = _get("/api/v1/query", query=promql)
    res = data["result"]
    if data["resultType"] == "scalar":
        return f"Wert: {_num(res[1])}"
    lines = [f"{_labels(r['metric'])} {_num(r['value'][1])}" for r in res[:MAX_SERIES]]
    more = f"\n… {len(res) - MAX_SERIES} weitere Serien" if len(res) > MAX_SERIES else ""
    return f"{len(res)} Serien:\n" + "\n".join(lines) + more if res else "Keine Daten."


@mcp.tool()
def promql_verlauf(promql: str, stunden: float = 24, schritt_minuten: int = 0) -> str:
    """Verlauf eines PromQL-Ausdrucks über die letzten Stunden (max. 168), zusammengefasst pro Serie:
    Minimum, Durchschnitt, Maximum, letzter Wert und Zeitpunkt des Maximums. Für Fragen wie
    "Wann war die CPU am höchsten?" oder "Wie hat sich der Speicher entwickelt?"."""
    stunden = max(0.1, min(float(stunden), 168))
    step = schritt_minuten * 60 if schritt_minuten > 0 else max(60, int(stunden * 3600 / 200))
    end = time.time()
    data = _get("/api/v1/query_range", query=promql, start=end - stunden * 3600, end=end, step=step)
    res = data["result"]
    if not res:
        return "Keine Daten."
    lines = []
    for r in res[:MAX_SERIES]:
        vals = [(t, float(v)) for t, v in r["values"] if v not in ("NaN", "+Inf", "-Inf")]
        if not vals:
            continue
        nums = [v for _, v in vals]
        tmax = max(vals, key=lambda x: x[1])[0]
        lines.append(f"{_labels(r['metric'])}: min {_num(str(min(nums)))}, Ø {_num(str(sum(nums) / len(nums)))}, "
                     f"max {_num(str(max(nums)))} (um {time.strftime('%d.%m. %H:%M', time.localtime(tmax))}), "
                     f"zuletzt {_num(str(nums[-1]))}")
    return f"Letzte {stunden:g} h, Schritt {step // 60} min, {len(res)} Serien:\n" + "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
