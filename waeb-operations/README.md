# Monitoring Maxcluster (readonly)

Docker-Setup, um Dateien und Loki-Logs auf Maxcluster nur lesend anzusehen.
Alles läuft über den SFTP-User `sftp-user-1` („Nur lesender Zugriff“, keine Shell).

| Was | URL |
|---|---|
| Dateien (nur lesen) | http://localhost:8080 |
| Open WebUI **PROD** | https://waeb-operations.oryn.brandadrian.com (lokal http://localhost:3010) |
| Open WebUI **STAGING** | https://waeb-operations-staging.oryn.brandadrian.com (lokal http://localhost:3011) |
| Grafana (nur lokal): PROD Logs, STAGING Logs, Server | http://localhost:3020 |
| Prometheus über Tunnel | http://localhost:9190 |
| Loki über Tunnel | http://localhost:3110/ready |
| MySQL über Tunnel | 127.0.0.1:3316 |

Container: `tunnel` (autossh zu Loki auf dem Cluster), `files` (rclone `serve http --read-only`), `loki-mcp` (nur GET auf Loki), `open-webui`.

## PROD und STAGING strikt getrennt

Alles, was Shop-Daten liefert, gibt es doppelt, mit eigenem Container, eigenen Zugangsdaten und eigener Tool-ID:

| Bereich | PROD (www.geschenkkoerbe.ch) | STAGING (shopware-staging.geschenkkoerbe.ch) | harte Sperre |
|---|---|---|---|
| Shopware Admin API | `shopware-mcp-prod` (`server:shopware-prod`), **nur lesend** | `shopware-mcp-staging` (`server:shopware-staging`) | eigene Integration + eigener Key (`MCPO_*_KEY`); PROD: schreibende Tools ausgeblendet und mit 403 gesperrt (`SHOPWARE_PROD_READONLY`) |
| Logs (Loki) | `loki-mcp-prod`: job `shopware`, `varlogs` | `loki-mcp-staging`: job `shopware_stage`, `varlogs` | `LOKI_ALLOWED_JOBS`: jede Abfrage braucht einen erlaubten `job` |
| Dateien (SFTP) | `files-mcp-prod`: `shopware.geschenkkoerbe.ch/`, `logs/` | `files-mcp-staging`: `shopware-staging.geschenkkoerbe.ch/`, `logs/` | `FILES_ALLOWED_ROOTS`, auch gegen `../` |
| MySQL | `mysql-mcp-prod`: `MYSQL_PROD_*` | `mysql-mcp-staging`: `MYSQL_STAGING_*` | eigene User, genau eine Datenbank pro Instanz |
| Server-Metriken | `metrics-mcp` (gemeinsam, gehört zum Server) | | |

Open WebUI läuft **zweimal**: `open-webui-prod` (WAEB PROD) und `open-webui-staging` (WAEB STAGING), mit eigener Domain, eigenem Volume (Chats, Benutzer) und eigenem `WEBUI_*_SECRET_KEY`. Jede Instanz kennt nur die Tool-Server ihrer Umgebung plus Server-Metriken; die Tools der anderen Umgebung existieren dort gar nicht. Modelle pro Instanz: **Schnell / Gründlich / Analyse** (`openwebui/models.json`, eingespielt von `setup-prod` bzw. `setup-staging`), Basismodelle ausgeblendet. Alle MCPs sind nur im internen Docker-Netz erreichbar.

Grafana bleibt eine Instanz, aber mit getrennten Dashboards: **PROD Logs**, **STAGING Logs** und **Server** (Metriken und `/var/log`).

Test der Trennung: `tests/trennung.py` (Anleitung im Kopf der Datei).

## Einmalig einrichten

```bash
# 1. Key erstellen (ohne Passphrase) und Public Key im Managed Center beim SFTP-User eintragen
ssh-keygen -t ed25519 -f ~/.ssh/id_maxcluster_ro -N "" -C "maxcluster-readonly"
cat ~/.ssh/id_maxcluster_ro.pub

# 2. .env anlegen (Pfade sind absolut, kein Passwort)
cp .env.example .env
```

Optional in `~/.ssh/config`:

```
Host maxcluster-ro
  HostName 185.88.214.149
  User sftp-user-1
  IdentityFile ~/.ssh/id_maxcluster_ro
  IdentitiesOnly yes
```

## Docker

```bash
docker compose up -d --build        # starten
docker compose ps                   # Status
docker compose logs -f tunnel files # Logs ansehen
curl -s http://localhost:3110/ready # "ready"
docker compose down                 # stoppen
```

## Open WebUI

Beim ersten Start (leeres Volume) wird aus der `.env` automatisch angelegt:
- Admin-Konto `WEBUI_ADMIN_EMAIL` / `WEBUI_ADMIN_PASSWORD`, Registrierung ist danach aus.
- LLM: über die Oryn-API mit Key (`LLM_API_BASE_URL`, `LLM_API_KEY`), damit es auch auf einem anderen Rechner läuft. Optional zusätzlich Ollama direkt ohne Key mit `ENABLE_OLLAMA=true` (nur auf dem Ollama-Rechner). Angeboten werden nur die Modelle aus `MODEL_IDS_JSON` (Default 35B-A3B Q4, 27B, 27B Analyse), Standard `DEFAULT_MODEL`.
- MCP-Verbindung „Loki Maxcluster“ zu `http://loki-mcp:8000/mcp`, bei jedem Modell standardmäßig eingeschaltet (`server:mcp:loki`), native Tool-Aufrufe.
- Lokale Ports: Open WebUI PROD 3010, STAGING 3011, Grafana 3020, Loki 3110, MySQL 3316, Prometheus 9190 (3000, 3100, 9090 sind hier schon belegt). Anpassbar über `WEBUI_PROD_HOST_PORT`, `WEBUI_STAGING_HOST_PORT`, `GRAFANA_HOST_PORT`, `LOKI_HOST_PORT`, `MYSQL_HOST_PORT`, `PROMETHEUS_HOST_PORT`.

Mit `ENABLE_PERSISTENT_CONFIG=false` gelten Änderungen an Modell- und MCP-Einstellungen nach `docker compose up -d`. Nur das Admin-Konto wird einmalig angelegt; um es neu anzulegen, das Volume zurücksetzen:

```bash
docker compose down
docker volume rm waeb-operations_open-webui waeb-operations_open-webui-staging   # löscht Konten und Chats
docker compose up -d
```

## Datei-MCP (Dateien suchen und lesen)

`files-mcp` (Python, `mcp/files/server.py`) gibt Open WebUI vier nur lesende Tools über denselben SFTP-User wie `files`:

| Tool | Wofür |
|---|---|
| `ordner_auflisten` | Inhalt eines Ordners mit Grösse und Datum |
| `dateien_suchen` | Dateinamen nach Muster (`*.log`, `*config*.yml`), neueste zuerst |
| `datei_lesen` | Datei oder Ausschnitt; `ab_zeile` negativ = Ende einer Datei (z. B. -100) |
| `inhalt_suchen` | Text/Regex in den Dateien eines Ordners, wie grep |

Der SFTP-User hat keine Shell: Für die Inhaltssuche wird jede Datei übertragen. Limits (per Env änderbar): 400 Dateien, 2 MB pro Datei, 200 KB pro Lesen, 300 Treffer, 60 s. Grosse Ordner wie `vendor`, `node_modules`, Caches, Media, Backups und `releases` werden standardmässig übersprungen (`auch_grosse_ordner=true` schaltet das ab). Eine Suche ab der Wurzel läuft meist ins Zeitlimit; besser einen Ordner angeben, z. B. `shopware.geschenkkoerbe.ch/deployer/current/custom/plugins`.

## MySQL-MCP (Shopware-Datenbanken)

`mysql-mcp` (Python, `mcp/mysql/server.py`) fragt die Shopware-Datenbanken über den SSH-Tunnel ab (der Tunnel leitet zusätzlich `127.0.0.1:3306` auf dem Server weiter). Tools: `umgebungen`, `tabellen_auflisten`, `tabelle_beschreiben`, `sql_abfrage`.

Nur lesend, dreifach abgesichert:
1. **Lese-User verwenden** (nur `SELECT`, `SHOW VIEW`), nie den Shopware-App-User.
2. Nur eine Anweisung, die mit `SELECT`, `WITH`, `SHOW`, `DESCRIBE` oder `EXPLAIN` beginnt; `INTO OUTFILE`, `FOR UPDATE`, `SLEEP`, `SET` usw. werden abgelehnt.
3. Jede Abfrage läuft in `START TRANSACTION READ ONLY` mit `MAX_EXECUTION_TIME` (30 s) und wird zurückgerollt; höchstens 500 Zeilen.

In der `.env`, je Umgebung ein eigener Lese-User:

```
MYSQL_PROD_USER=waeb_ro_prod
MYSQL_PROD_PASSWORD=<passwort>
MYSQL_PROD_DB=<db_prod>
MYSQL_STAGING_USER=waeb_ro_staging
MYSQL_STAGING_PASSWORD=<passwort>
MYSQL_STAGING_DB=<db_staging>
```

Lese-User anlegen (Maxcluster Managed Center oder als DB-Admin), Verbindungen kommen über den Tunnel von `127.0.0.1`:

```sql
CREATE USER 'waeb_ro_prod'@'127.0.0.1' IDENTIFIED BY '<passwort>';
GRANT SELECT, SHOW VIEW ON `<db_prod>`.* TO 'waeb_ro_prod'@'127.0.0.1';
CREATE USER 'waeb_ro_staging'@'127.0.0.1' IDENTIFIED BY '<passwort>';
GRANT SELECT, SHOW VIEW ON `<db_staging>`.* TO 'waeb_ro_staging'@'127.0.0.1';
```

Danach `docker compose up -d mysql-mcp-prod mysql-mcp-staging`.

## Agenten und Modelle

`openwebui/models.json` legt fest, was der Dienst `setup-prod`/`setup-staging` in der jeweiligen Instanz anlegt:

| Agent | Basis | Tools (nur eigene Umgebung) | Skills |
|---|---|---|---|
| 🛒 **Shop · Bestellungen & Administration** (`<env>-shop`, Standard) | 35B-A3B (schnell) | Shopware, MySQL | Bestellungen, Bestellstatus, Stammkunden, Umsatz, Vorjahr, Produkte/Lager, Shop-Suche, MySQL |
| 🔧 **Technik · Logs, Fehler & Datenbank** (`<env>-technik`) | 27B (gründlich) | Logs, Dateien, MySQL, Server-Metriken, Shopware | Log-Suche, Datei-Suche, MySQL, Server-Metriken |

Der Technik-Agent arbeitet nach einem festen Ablauf (Zeitfenster festlegen, erst zählen dann lesen, mit Metriken korrelieren, Symptom von Ursache trennen) und antwortet mit Befund, Ursache, Belegen und nächsten Schritten. Log-, Datei- und DB-Inhalte behandelt er als Daten, nicht als Anweisungen.
Zusätzlich gibt es die freien Modelle **Schnell / Gründlich / Analyse** mit allen Tools der Umgebung. Die Basismodelle sind ausgeblendet.

## Skills

Drei einfache Skills in `openwebui/skills/<id>/SKILL.md`, die der Dienst `setup` bei jedem `docker compose up -d` in Open WebUI einspielt (für alle Benutzer). Das Modell sieht nur Name und Beschreibung und lädt einen Skill, wenn die Frage passt.

| Skill | Wofür |
|---|---|
| `log-suche` | Loki: Quellen (Production, Staging, Server), Log-Format, LogQL-Beispiele |
| `datei-suche` | Dateien: wichtige Ordner, Vorgehen, keine Zugangsdaten zitieren |
| `mysql-abfragen` | MySQL: Shopware-Besonderheiten (binäre IDs, version_id), wichtige Tabellen, Beispiel-SQL |
| `server-metriken` | Prometheus: fertige PromQL-Ausdrücke für CPU, RAM, Disk, Last, Netz |

Nur Skills geändert: `docker compose up -d setup-prod setup-staging`.

## Log-Dashboard (Grafana)

Eigenes Grafana unter http://localhost:3020 (Login `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` aus der `.env`, anonymer Zugriff aus). Bewusst nicht im öffentlichen Oryn-Grafana, weil dort anonymer Lesezugriff aktiv ist.
Datenquelle „Loki Maxcluster“ über den Tunnel, Dashboard „Maxcluster Logs“ (Startseite) mit drei Bereichen:

| Bereich | Loki-Selektor | Inhalt |
|---|---|---|
| Production | `{job="shopware"}` | Shopware-Logs von www.geschenkkoerbe.ch: Fehler, Kritisch, Warnungen, Fehler pro Kanal, häufigste Fehler, Log-Liste |
| Staging | `{job="shopware_stage"}` | gleich aufgebaut. **Achtung:** liest zurzeit dieselben Dateien wie Production (siehe unten) |
| Server | `{job="varlogs"}` | `/var/log`: SSH-Fehlanmeldungen, PHP-FPM, Zertifikate (lego), Zeilen pro Datei, Log-Liste ohne Cron |

Bekanntes Problem: Promtail auf dem Server ist für `shopware_stage` auf `/var/www/share/shopware.geschenkkoerbe.ch/deployer/shared/var/log/` konfiguriert (= Production). Richtig wäre `/var/www/share/shopware-staging.geschenkkoerbe.ch/deployer/shared/var/log/`. Muss auf dem Server korrigiert werden (der SFTP-User ist nur lesend).

Dashboard und Datenquelle liegen in `grafana/` und werden beim Start provisioniert; Änderungen an der JSON-Datei übernimmt Grafana nach spätestens 30 s.

## Öffentlich über Traefik

Beide Open-WebUI-Instanzen hängen im Docker-Netz `proxy`; Traefik liefert sie unter `https://${WAEB_PROD_HOST}` (Default `waeb-operations.oryn.brandadrian.com`) und `https://${WAEB_STAGING_HOST}` (Default `waeb-operations-staging.oryn.brandadrian.com`) aus, Zertifikat über `le`. Anmeldung nötig, Registrierung aus. Tunnel, MCPs und Grafana haben keine Traefik-Route; der Datei-Browser bleibt lokal (127.0.0.1:8080).
In der `.env` nötig: `WEBUI_PROD_SECRET_KEY` und `WEBUI_STAGING_SECRET_KEY` (feste Zufallswerte).

## Ohne Docker

```bash
sftp maxcluster-ro                                   # Dateien: ls, cd, get, exit
echo "ls -la" | sftp -q maxcluster-ro                # einzelner Befehl
ssh -N -L 3110:127.0.0.1:3100 maxcluster-ro          # Loki-Tunnel auf localhost:3110 (3100 ist hier vom lokalen Loki belegt)
```

`ssh maxcluster-ro` ohne `-N` gibt „Shell access is disabled“. Das ist gewollt.

## Auf einen anderen Rechner mitnehmen

```bash
sh pack.sh         # erstellt ~/Desktop/monitoring-portable.zip inkl. Key, known_hosts und .env
```

Auf dem anderen Rechner: entpacken, `cd monitoring`, `docker compose up -d --build`.
Die ZIP enthält Secrets (Key, LLM-Key, Passwort): nicht committen, nicht per Mail verschicken, danach löschen.

## Sicherheit

- SFTP-User nur lesend, keine Shell (im Managed Center gesetzt).
- Key wird read-only gemountet, `.env` ist in `.gitignore`.
- Ports nur auf `127.0.0.1`.
