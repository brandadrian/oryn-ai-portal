---
name: Log-Suche Maxcluster
description: Logs vom Maxcluster-Server mit dem Loki-Tool durchsuchen - Shopware Production, Staging und Server-Logs (/var/log). Laden bei Fragen nach Fehlern, Exceptions, Warnungen, SSH-Anmeldungen oder was im Shop/auf dem Server passiert ist.
---

# Log-Suche (Loki, nur lesen)

Tool: `loki_query_range` (LogQL, max. 24 h, max. 500 Zeilen). Für Zählungen `count_over_time` statt Zeilen holen.

## Quellen (Label `job`)

Jedes Modell darf nur die job-Werte seiner Umgebung abfragen: PROD `shopware` + `varlogs`, STAGING `shopware_stage` + `varlogs`. Andere Werte lehnt das Tool ab.

| job | Inhalt |
|---|---|
| `shopware` | Shopware **Production** (www.geschenkkoerbe.ch), Dateien `…/var/log/<kanal>-JJJJ-MM-TT.log` |
| `shopware_stage` | **Staging** – liest zurzeit dieselben Dateien wie Production (Fehlkonfiguration). Ergebnisse immer mit diesem Hinweis nennen. |
| `varlogs` | Server: `/var/log/auth.log` (SSH, Cron), `php*-fpm.log`, `lego.log` (Zertifikate), `vsftpd.log`, `dpkg.log` |

## Shopware-Zeilen

Format: `[2026-11-21T13:28:19+00:00] kanal.LEVEL: Meldung [] []`. Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.

Zerlegen: ``| regexp `\] (?P<channel>[A-Za-z0-9_-]+)\.(?P<level>[A-Z]+): (?P<msg>[^\[{]{0,160})` ``

## Beispiele

- Fehler der letzten Stunde: `{job="shopware"} |~ "\.(ERROR|CRITICAL):"` mit `sinceMinutes: 60`
- Nur ein Plugin: `{job="shopware", filename=~".*/waeb_supplier_order_processing-.*"} |= "ERROR"`
- Text suchen (gross/klein egal): `{job="shopware"} |~ "(?i)bestellnummer 40012345"`
- Fehler pro Kanal zählen: `sum by (channel) (count_over_time({job="shopware"} | regexp `…` | level=~"ERROR|CRITICAL" [24h]))`
- SSH-Fehlversuche: `{job="varlogs", filename="/var/log/auth.log"} |~ "Failed password|Invalid user"`
- PHP-FPM-Probleme: `{job="varlogs", filename=~"/var/log/php.*-fpm.log"} |~ "WARNING|ERROR"`

## Regeln

- Immer `job` angeben, Zeitraum so kurz wie möglich.
- Zeiten in den Logs sind UTC.
- Keine Werte erfinden: nur berichten, was die Abfrage liefert. Bei 500 Zeilen Limit enger filtern.
