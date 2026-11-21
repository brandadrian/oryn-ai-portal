---
name: Server-Metriken Maxcluster
description: Auslastung des Maxcluster-Servers mit dem Prometheus-Tool - CPU, RAM, Disk, Last, Netzwerk, jetzt und im Verlauf. Laden bei Fragen wie "ist der Server ausgelastet", "wie voll ist die Disk", "warum war der Shop langsam".
---

# Server-Metriken (Prometheus, nur lesen)

Tools: `server_zustand` (Überblick jetzt), `promql_abfrage` (ein Wert jetzt), `promql_verlauf` (min/Ø/max über Stunden), `metriken_auflisten`.

Quelle: node_exporter auf dem Server (`instance="localhost:9100"`), 6 Kerne, ca. 23 GB RAM. `/var/lib/mysql` ist ein Netzwerkspeicher.

## Fertige Ausdrücke

| Frage | PromQL |
|---|---|
| CPU % | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))` |
| CPU nach Art (iowait, steal …) | `100 * avg by (mode) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))` |
| RAM % | `100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)` |
| Disk / % | `100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})` |
| Last pro Kern | `node_load5 / scalar(count(node_cpu_seconds_total{mode="idle"}))` |
| Netz ein/aus (Byte/s) | `rate(node_network_receive_bytes_total{device="eth0"}[5m])`, `…transmit…` |

## Vorgehen

- Zuerst `server_zustand`, danach gezielt `promql_verlauf` (z. B. 24 h oder 7 Tage = 168 h).
- Für „warum war es langsam um 14 Uhr“: Verlauf von CPU, iowait und Last ansehen, dazu mit dem Log-Skill die Fehler im selben Zeitraum prüfen.
- Grenzwerte als Faustregel: CPU > 80 %, RAM > 90 %, Disk > 90 %, Last pro Kern > 1 = auffällig.
- Nur gemessene Werte nennen, nichts schätzen.
