import json, sys

OUT = sys.argv[1]
DS = {"type": "prometheus", "uid": "prometheus-maxcluster"}
I = 'instance="localhost:9100"'
pid = [0]


def nid():
    pid[0] += 1
    return pid[0]


def steps(*a):
    return [{"color": c, "value": v} for c, v in a]


def stat(title, expr, x, y, unit, st, desc, dec=0, w=4):
    return {"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": 4, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "expr": expr, "instant": True}],
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "value", "graphMode": "area", "textMode": "value"},
            "fieldConfig": {"defaults": {"unit": unit, "decimals": dec,
                                         "thresholds": {"mode": "absolute", "steps": st}}, "overrides": []}}


def ts(title, targets, x, y, unit, desc, w=12, h=8, stack=False, mx=None):
    d = {"unit": unit, "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 15 if not stack else 40,
                                  "stacking": {"mode": "normal" if stack else "none"}, "showPoints": "never"}}
    if mx is not None:
        d["max"] = mx
        d["min"] = 0
    return {"id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l} for i, (e, l) in enumerate(targets)],
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}}}


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


CPU = f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle",{I}}}[5m])))'
RAM = f'100 * (1 - node_memory_MemAvailable_bytes{{{I}}} / node_memory_MemTotal_bytes{{{I}}})'
DISK = f'100 * (1 - node_filesystem_avail_bytes{{mountpoint="/",{I}}} / node_filesystem_size_bytes{{mountpoint="/",{I}}})'
LOAD = f'node_load5{{{I}}} / scalar(count(node_cpu_seconds_total{{mode="idle",{I}}}))'
UP = f'time() - node_boot_time_seconds{{{I}}}'
PCT = steps(("green", None), ("orange", 70), ("red", 90))

p, y = [], 0
p.append(row("Jetzt", y)); y += 1
p += [
    stat("CPU", CPU, 0, y, "percent", PCT, "Durchschnittliche CPU-Auslastung aller 6 Kerne (5 min).", 0),
    stat("RAM belegt", RAM, 4, y, "percent", PCT, "Belegter Arbeitsspeicher ohne Cache (MemAvailable).", 0),
    stat("Disk / belegt", DISK, 8, y, "percent", steps(("green", None), ("orange", 80), ("red", 90)), "Belegung der Systempartition /.", 0),
    stat("Last pro Kern", LOAD, 12, y, "none", steps(("green", None), ("orange", 1), ("red", 2)), "Load (5 min) geteilt durch Anzahl Kerne. Über 1 = mehr Arbeit als Kerne.", 2),
    stat("Netz eingehend", f'rate(node_network_receive_bytes_total{{device="eth0",{I}}}[5m])', 16, y, "Bps", steps(("blue", None)), "Eingehender Netzverkehr auf eth0.", 1),
    stat("Läuft seit", UP, 20, y, "s", steps(("blue", None)), "Zeit seit dem letzten Neustart des Servers.", 0),
]
y += 4
p.append(row("Verlauf", y)); y += 1
p += [
    ts("CPU nach Art", [(f'100 * avg by (mode) (rate(node_cpu_seconds_total{{mode!="idle",{I}}}[5m]))', "{{mode}}")], 0, y, "percent",
       "CPU-Zeit nach Art: user (PHP, MySQL …), system (Kernel), iowait (warten auf Disk), steal (vom Hoster abgezogen).", stack=True),
    ts("Arbeitsspeicher", [(f'node_memory_MemTotal_bytes{{{I}}} - node_memory_MemAvailable_bytes{{{I}}}', "belegt"),
                           (f'node_memory_Cached_bytes{{{I}}} + node_memory_Buffers_bytes{{{I}}}', "Cache/Buffer"),
                           (f'node_memory_MemTotal_bytes{{{I}}}', "gesamt")], 12, y, "bytes",
       "Belegter Speicher, Datei-Cache und Gesamtspeicher (22 GB)."),
]
y += 8
p += [
    ts("Last (Load)", [(f'node_load1{{{I}}}', "1 min"), (f'node_load5{{{I}}}', "5 min"), (f'node_load15{{{I}}}', "15 min"),
                       (f'count(node_cpu_seconds_total{{mode="idle",{I}}})', "Kerne")], 0, y, "none",
       "Systemlast. Liegt sie dauerhaft über der Zahl der Kerne (6), wartet Arbeit."),
    ts("Disk-Belegung", [(f'100 * (1 - node_filesystem_avail_bytes{{mountpoint=~"/|/var/lib/mysql",{I}}} / node_filesystem_size_bytes{{mountpoint=~"/|/var/lib/mysql",{I}}})', "{{mountpoint}}")],
       12, y, "percent", "Belegung der Systempartition / und des MySQL-Speichers (/var/lib/mysql, Netzwerkspeicher).", mx=100),
]
y += 8
p += [
    ts("Disk lesen/schreiben", [(f'sum(rate(node_disk_read_bytes_total{{{I}}}[5m]))', "lesen"),
                                (f'sum(rate(node_disk_written_bytes_total{{{I}}}[5m]))', "schreiben")], 0, y, "Bps",
       "Lese- und Schreibrate aller lokalen Disks."),
    ts("Netzwerk eth0", [(f'rate(node_network_receive_bytes_total{{device="eth0",{I}}}[5m])', "eingehend"),
                         (f'rate(node_network_transmit_bytes_total{{device="eth0",{I}}}[5m])', "ausgehend")], 12, y, "Bps",
       "Netzverkehr der Netzwerkkarte eth0 (Besucher, Galaxus, Zahlungsanbieter …)."),
]
y += 8

dash = {"uid": "maxcluster-server", "title": "Maxcluster Server", "tags": ["maxcluster", "server", "prometheus"],
        "timezone": "browser", "schemaVersion": 39, "version": 1, "refresh": "1m", "time": {"from": "now-24h", "to": "now"},
        "description": "CPU, RAM, Disk, Last und Netzwerk des Maxcluster-Servers (Prometheus, node_exporter).",
        "links": [{"title": "Maxcluster Logs", "type": "link", "url": "/d/maxcluster-logs", "icon": "doc"}],
        "panels": p}
json.dump(dash, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(p))
