---
name: Datei-Suche Maxcluster
description: Dateien auf dem Maxcluster-Server finden und lesen (nur lesend) - Shopware-Code, Plugin-Konfigurationen, Server-Logs als Datei. Laden bei Fragen wie "wo liegt", "zeig mir die Datei", "in welcher Datei steht".
---

# Datei-Suche (SFTP, nur lesen)

Tools: `ordner_auflisten`, `dateien_suchen`, `datei_lesen`, `inhalt_suchen`. Pfade relativ zum Arbeitsordner, ohne führenden `/`.

## Wichtige Ordner

Jedes Modell sieht nur die Ordner seiner Umgebung: PROD `shopware.geschenkkoerbe.ch/` + `logs/`, STAGING `shopware-staging.geschenkkoerbe.ch/` + `logs/`.

| Pfad | Inhalt |
|---|---|
| `shopware.geschenkkoerbe.ch/deployer/current` | Production-Shop (aktuelles Release) |
| `shopware.geschenkkoerbe.ch/deployer/current/custom/plugins` | eigene Plugins (Waeb*, Geschenkkoerbe*, …) |
| `shopware.geschenkkoerbe.ch/deployer/shared/var/log` | Production-Logs als Dateien |
| `shopware-staging.geschenkkoerbe.ch/deployer/…` | Staging, gleich aufgebaut |
| `logs` | Server-Logs (nginx, php-fpm, auth, …) |

## Vorgehen

1. Unklar wo? Zuerst `ordner_auflisten` eine Ebene nach der anderen.
2. Dateinamen: `dateien_suchen` mit Muster (`*.xml`, `*config*`) und **immer einem Ordner** – ab der Wurzel läuft die Suche ins Zeitlimit.
3. Inhalt: `inhalt_suchen` mit engem Ordner und `dateimuster` (z. B. `*.php`). Limits: 400 Dateien, 2 MB pro Datei, 60 s.
4. Lesen: `datei_lesen`; für das Ende eines Logs `ab_zeile: -100`.

## Regeln

- Keine Zugangsdaten wiedergeben: Bei `.env`, `config/*.yaml` o. Ä. Passwörter, Keys und Tokens nie zitieren, nur sagen, dass sie dort stehen.
- `vendor`, Caches, Media, Backups und alte `releases` werden übersprungen; nur bei Bedarf `auch_grosse_ordner: true`.
- Steht „Suche unvollständig“ im Ergebnis, das so sagen und enger suchen.
