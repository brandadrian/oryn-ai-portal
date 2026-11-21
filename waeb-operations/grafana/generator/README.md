# Dashboards neu erzeugen

```powershell
cd grafana\dashboards
python ..\generator\mkserver.py maxcluster-server.json
python ..\generator\mklogs.py .\x.json
```

Zuerst `mkserver.py` (Metriken), dann `mklogs.py` (PROD Logs, STAGING Logs; hängt die Server-Logs an das Server-Dashboard an). Grafana übernimmt Änderungen nach spätestens 30 s.
