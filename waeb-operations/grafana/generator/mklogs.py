import json, sys

OUT = sys.argv[1]
DS = {"type": "loki", "uid": "loki-maxcluster"}
RX = r'regexp `\] (?P<channel>[A-Za-z0-9_-]+)\.(?P<level>[A-Z]+): (?P<msg>[^\[{]{0,160})`'
ERR = 'level=~"ERROR|CRITICAL|ALERT|EMERGENCY"'
CRIT = 'level=~"CRITICAL|ALERT|EMERGENCY"'
WARN = 'level="WARNING"'
SEARCH = ' |~ "(?i)$suche"'

pid = [0]


def nid():
    pid[0] += 1
    return pid[0]


def steps(*a):
    return [{"color": c, "value": v} for c, v in a]


def stat(title, expr, x, y, st, desc, w=6):
    return {"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": 4, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "expr": expr, "queryType": "instant"}],
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "value", "graphMode": "none", "textMode": "value"},
            "fieldConfig": {"defaults": {"unit": "short", "decimals": 0, "noValue": "0",
                                         "thresholds": {"mode": "absolute", "steps": st}}, "overrides": []}}


def row(title, y, desc=""):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


def bars(title, expr, legend, y, desc, x=0, w=12):
    return {"id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": 8, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "expr": expr, "queryType": "range", "legendFormat": legend}],
            "fieldConfig": {"defaults": {"unit": "short", "custom": {"drawStyle": "bars", "fillOpacity": 80, "lineWidth": 1,
                                                                     "stacking": {"mode": "normal"}}}, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}}}


def toptable(title, expr, y, desc, x=12, w=12):
    return {"id": nid(), "type": "table", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": 8, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "expr": expr, "queryType": "instant", "format": "table"}],
            "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True},
                                                               "indexByName": {"Value": 0, "channel": 1, "msg": 2},
                                                               "renameByName": {"Value": "Anzahl", "channel": "Kanal", "msg": "Meldung"}}}],
            "options": {"showHeader": True, "cellHeight": "sm", "sortBy": [{"displayName": "Anzahl", "desc": True}]},
            "fieldConfig": {"defaults": {"custom": {"align": "auto"}},
                            "overrides": [{"matcher": {"id": "byName", "options": "Anzahl"},
                                           "properties": [{"id": "custom.width", "value": 80}]},
                                          {"matcher": {"id": "byName", "options": "Kanal"},
                                           "properties": [{"id": "custom.width", "value": 240}]}]}}


def logs(title, expr, y, desc, h=10):
    return {"id": nid(), "type": "logs", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": h, "w": 24, "x": 0, "y": y},
            "targets": [{"refId": "A", "expr": expr, "queryType": "range", "maxLines": 500}],
            "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending", "enableLogDetails": True,
                        "dedupStrategy": "none", "prettifyLogMessage": False, "showLabels": False}}



def banner(label, color, host, job, extra=""):
    """Farbiges Kopf-Banner (HTML) für ein Umgebungs-Dashboard."""
    html = (
        f'<div style="display:flex;align-items:center;gap:18px;height:100%;padding:10px 18px;'
        f'border-left:6px solid {color};border-radius:6px;background:linear-gradient(90deg,{color}26,transparent 70%)">'
        f'<div style="font-size:30px;font-weight:700;letter-spacing:2px;color:{color}">{label}</div>'
        f'<div style="line-height:1.5">'
        f'<div style="font-size:17px;font-weight:600"><a href="https://{host}" target="_blank" style="color:inherit;text-decoration:none">{host} ↗</a></div>'
        f'<div style="opacity:.75;font-size:13px">Shop-Logs <code>job = {job}</code> · nur lesend · Suchfeld oben filtert die Log-Liste{extra}</div>'
        f'</div></div>'
    )
    return {"id": nid(), "type": "text", "title": "", "transparent": True, "gridPos": {"h": 3, "w": 24, "x": 0, "y": 0},
            "options": {"mode": "html", "content": html}}


def text(content, y, h=3):
    return {"id": nid(), "type": "text", "title": "", "gridPos": {"h": h, "w": 24, "x": 0, "y": y},
            "options": {"mode": "markdown", "content": content}, "transparent": False}


def shop_section(job, name, y, note=None):
    sel = '{job="' + job + '"}'
    P = []
    P.append(row(name, y)); y += 1
    if note:
        P.append(text(note, y)); y += 3
    P += [
        stat("Fehler", f'sum(count_over_time({sel} | {RX} | {ERR} [$__range]))', 0, y,
             steps(("green", None), ("orange", 1), ("red", 50)), "Zeilen mit Level ERROR, CRITICAL, ALERT oder EMERGENCY im gewählten Zeitraum."),
        stat("Kritisch", f'sum(count_over_time({sel} | {RX} | {CRIT} [$__range]))', 6, y,
             steps(("green", None), ("red", 1)), "Zeilen mit Level CRITICAL, ALERT oder EMERGENCY, z. B. unbehandelte Exceptions."),
        stat("Warnungen", f'sum(count_over_time({sel} | {RX} | {WARN} [$__range]))', 12, y,
             steps(("green", None), ("orange", 1)), "Zeilen mit Level WARNING."),
        stat("Log-Zeilen gesamt", f'sum(count_over_time({sel} [$__range]))', 18, y,
             steps(("blue", None)), "Alle Zeilen dieses Bereichs, inkl. INFO und DEBUG."),
    ]
    y += 4
    P += [
        bars("Fehler pro Kanal", f'sum by (channel) (count_over_time({sel} | {RX} | {ERR} [$__interval]))', "{{channel}}", y,
             "Fehler (ERROR und höher) über die Zeit, aufgeteilt nach Monolog-Kanal (Plugin bzw. Bereich)."),
        toptable("Häufigste Fehler", f'topk(15, sum by (channel, msg) (count_over_time({sel} | {RX} | {ERR} [$__range])))', y,
                 "Die 15 häufigsten Fehlermeldungen im Zeitraum, ohne Kontext-Daten am Zeilenende."),
    ]
    y += 8
    P.append(logs("Fehler und Warnungen", f'{sel} | {RX} | level=~"WARNING|ERROR|CRITICAL|ALERT|EMERGENCY"{SEARCH}', y,
                  "Rohzeilen mit Level WARNING und höher, neueste oben. Das Suchfeld oben filtert zusätzlich."))
    y += 10
    return P, y




# ---------------- Ausgabe: je ein Dashboard PROD, STAGING; Server-Logs ins Server-Dashboard ----------------
import os
OUTDIR = os.path.dirname(OUT) if OUT.endswith(".json") else OUT

SUCHE = {"name": "suche", "label": "Suche in Log-Listen", "type": "textbox", "query": "", "current": {"text": "", "value": ""}}
LINKS = [{"title": "PROD Logs", "type": "link", "url": "/d/prod-logs", "icon": "doc"},
         {"title": "STAGING Logs", "type": "link", "url": "/d/staging-logs", "icon": "doc"},
         {"title": "Server", "type": "link", "url": "/d/maxcluster-server", "icon": "dashboard"}]


def write(uid, title, desc, panels, templating, tags):
    d = {"uid": uid, "title": title, "tags": tags, "timezone": "browser", "schemaVersion": 39, "version": 1,
         "refresh": "1m", "time": {"from": "now-24h", "to": "now"}, "links": LINKS, "description": desc,
         "templating": {"list": templating}, "panels": panels}
    json.dump(d, open(os.path.join(OUTDIR, uid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", uid, len(panels))


# PROD
pid[0] = 0
p, y = [banner("PRODUCTION", "#E02F44", "www.geschenkkoerbe.ch", "shopware")], 3
sp, y = shop_section("shopware", "Production – www.geschenkkoerbe.ch  (job = shopware)", y)
write("prod-logs", "PROD Logs", "Logs des Production-Shops www.geschenkkoerbe.ch.", p + sp, [SUCHE], ["prod", "logs"])

# STAGING
pid[0] = 0
p, y = [banner("STAGING", "#F2A20C", "shopware-staging.geschenkkoerbe.ch", "shopware_stage")], 3
sp, y = shop_section("shopware_stage", "Staging – shopware-staging.geschenkkoerbe.ch  (job = shopware_stage)", y,
                     note="⚠️ **Staging liefert im Moment keine eigenen Logs.** Promtail liest für `shopware_stage` dieselben Dateien wie für Production "
                          "(`/var/www/share/shopware.geschenkkoerbe.ch/deployer/shared/var/log/`). Die Zahlen hier sind deshalb eine Kopie von Production. "
                          "Die echten Staging-Logs liegen unter `/var/www/share/shopware-staging.geschenkkoerbe.ch/deployer/shared/var/log/` und müssen in der Promtail-Konfiguration auf dem Server eingetragen werden.")
write("staging-logs", "STAGING Logs", "Logs des Staging-Shops shopware-staging.geschenkkoerbe.ch.", p + sp, [SUCHE], ["staging", "logs"])

# SERVER: Server-Logs (varlogs) an das Server-Dashboard anhängen
srv_path = os.path.join(OUTDIR, "maxcluster-server.json")
srv = json.load(open(srv_path, encoding="utf-8"))
srv["panels"] = [x for x in srv["panels"] if x.get("datasource", {}).get("type") != "loki" and not (x.get("type") == "row" and "/var/log" in x.get("title", ""))]
y = max(x["gridPos"]["y"] + x["gridPos"]["h"] for x in srv["panels"])
pid[0] = 100
sel = '{job="varlogs"}'
SSH_FAIL = '|~ "Failed password|Invalid user|authentication failure|Connection closed by authenticating user"'
add = [row("Server-Logs – /var/log  (job = varlogs, gemeinsam für PROD und STAGING)", y)]
y += 1
add += [
    stat("SSH: fehlgeschlagene Anmeldungen", f'sum(count_over_time({{job="varlogs", filename="/var/log/auth.log"}} {SSH_FAIL} [$__range]))', 0, y,
         steps(("green", None), ("orange", 50), ("red", 1000)), "Fehlgeschlagene oder ungültige SSH-Anmeldeversuche laut auth.log (meist automatisierte Scans)."),
    stat("PHP-FPM: Warnungen/Fehler", f'sum(count_over_time({{job="varlogs", filename=~"/var/log/php.*-fpm.log"}} |~ "WARNING|ERROR|ALERT" [$__range]))', 6, y,
         steps(("green", None), ("orange", 1), ("red", 50)), "Warnungen und Fehler der PHP-FPM-Pools (z. B. max_children erreicht, langsame Requests)."),
    stat("Zertifikate (lego)", f'sum(count_over_time({{job="varlogs", filename="/var/log/lego.log"}} |~ "(?i)error|fail" [$__range]))', 12, y,
         steps(("green", None), ("red", 1)), "Fehler beim Erneuern der Let's-Encrypt-Zertifikate (lego.log)."),
    stat("Log-Zeilen gesamt", f'sum(count_over_time({sel} [$__range]))', 18, y, steps(("blue", None)), "Alle Zeilen aus /var/log im Zeitraum."),
]
y += 4
add += [
    bars("Zeilen pro Datei", f'sum by (filename) (count_over_time({sel} [$__interval]))', "{{filename}}", y,
         "Wie viel jede Datei in /var/log schreibt. auth.log ist meist am grössten (Cron und SSH)."),
    bars("SSH-Anmeldeversuche", f'sum(count_over_time({{job="varlogs", filename="/var/log/auth.log"}} {SSH_FAIL} [$__interval]))', "fehlgeschlagen", y,
         "Fehlgeschlagene SSH-Anmeldungen über die Zeit.", x=12),
]
y += 8
add.append(logs("Server-Logs (ohne Cron-Rauschen)", '{job="varlogs", filename=~"$datei"} != "pam_unix(cron:session)" != "CRON["' + SEARCH, y,
                "Rohzeilen aus /var/log. Die Datei-Auswahl oben schränkt ein, Cron-Sitzungsmeldungen sind ausgeblendet.", h=12))
srv["panels"] += add
srv["links"] = LINKS
srv["title"] = "Server (Metriken und /var/log)"
srv["templating"] = {"list": [SUCHE, {"name": "datei", "label": "Server-Datei", "type": "query", "datasource": DS,
                                      "query": {"label": "filename", "refId": "A", "stream": '{job="varlogs"}', "type": 1},
                                      "definition": 'label_values({job="varlogs"}, filename)', "includeAll": True, "multi": True, "allValue": ".*",
                                      "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "refresh": 2}]}
json.dump(srv, open(srv_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok server", len(srv["panels"]))
