# Shopware Chat

Separates Open WebUI mit Shopware-Tool, Modell und Benutzern fertig eingerichtet. Läuft neben dem normalen [Open WebUI](../openwebui/README.md), ohne es zu berühren (eigenes Projekt, Volume und eigene Domain).

## Instanzen

Eine Compose-Datei, pro Instanz eine Env-Datei (alle gitignored):

| Instanz | Env-Datei | Domain | Modell | Benutzer |
|---------|-----------|--------|--------|----------|
| staging | `.env.staging` | shopware-chat-staging.oryn.brandadrian.com | Ollama | Admin |
| production | `.env.production` | shopware-chat.oryn.brandadrian.com | Ollama | Admin |
| geschenkkoerbe | `.env.geschenkkoerbe` | geschenkkoerbe.oryn.brandadrian.com | OpenAI | Admin + einfacher Benutzer |

```bash
cp .env.example .env.<instanz>    # ausfüllen, APP_ENV=<instanz>
docker compose --env-file .env.<instanz> up -d
```

Alle Einstellungen kommen bei jedem Start aus der Env-Datei (`ENABLE_PERSISTENT_CONFIG=false`), Änderungen im Admin-Menü gelten nur bis zum Neustart.

## Shopware vorbereiten

Als MCP-Server läuft [@shopware-ag/admin-mcp](https://github.com/shopware/shopware-admin-mcp) (Admin API, funktioniert auch mit Shopware 6.6) hinter [mcpo](https://github.com/open-webui/mcpo), das ihn Open WebUI als OpenAPI-Tool anbietet. Das Paket ist archiviert, die Version ist fest auf 0.1.1 gesetzt.

1. Admin → Einstellungen → System → Integrationen → Integration anlegen, z.B. "Open WebUI".
2. Rechte: Produkte, Kategorien, Verkaufskanäle, Medien, Steuern, Themes und Bestellungen. Für production eine eigene Rolle statt "Administrator".
3. Zugangs-ID → `SHOPWARE_CLIENT_ID`, Sicherheitsschlüssel → `SHOPWARE_CLIENT_SECRET`, Shop-Basis-URL (ohne `/api`) → `SHOPWARE_URL`.

Tools: Produkte, Kategorien, Bestellungen, Verkaufskanäle, Theme-Konfiguration, Medien-Upload und allgemeine Abfragen (`fetch_entity_list`, `dal_aggregate`). Achtung: Die Tools können auch schreiben und löschen, auch für den einfachen Benutzer.

## Was vorkonfiguriert ist

- Admin aus `WEBUI_ADMIN_EMAIL` / `WEBUI_ADMIN_PASSWORD`, wird beim ersten Start angelegt. Registrierung ist aus.
- Optional ein einfacher Benutzer aus `CHAT_USER_*`, angelegt vom Dienst `setup` (`setup.py`) nach dem Start. Er sieht keine Chat-Steuerung, keinen Systemprompt, keine Parameter, keinen Workspace, keine Websuche, Notizen, Kanäle oder Erinnerungen, nur den Chat.
- Standardmodell `DEFAULT_MODEL`, angepinnt. Bei OpenAI (`ENABLE_OPENAI=true`) wird nur dieses eine Modell angeboten.
- `setup.py` legt das Standardmodell als Workspace-Modell an (bzw. aktualisiert es bei jedem `up`): Systemprompt, Tool "Shopware" eingeschaltet, für alle Benutzer sichtbar, Funktionsaufruf nativ. Der Systemprompt steht in `docker-compose.yml` beim Dienst `setup`.
- Zusätzliches Tool `shopware_search` (in `limit-proxy.py`): nur lesende Suche über `/api/search/<entity>` mit vollen Shopware-Kriterien (Datumsbereich, Assoziationen, includes, Aggregationen). Damit reicht z.B. für "alle Bestellnummern mit Nusstorte der letzten 30 Tage" eine Abfrage (0,3 s) statt dutzender Einzelaufrufe.
- Alle Container hängen nur im Netz `proxy` (mit eindeutigen Aliasen `webui-<APP_ENV>` und `shopware-mcp-<APP_ENV>`), weil Docker Desktop beim Neuerstellen ein zweites Netz mehrfach nicht verbunden hat. `shopware-mcp` ist nicht über Traefik veröffentlicht und mit `MCPO_API_KEY` geschützt.
- Vor mcpo sitzt `limit-proxy.py`: macht Tool-Antworten verlustfrei kompakt (JSON ohne Einrückung, leere Felder weg; nur wenn eine Terms-Aggregation sonst zu groß wäre, werden Einträge mit count 1 als Anzahl zusammengefasst). Ist eine Antwort danach noch größer als `MAX_TOOL_RESULT_CHARS` (Standard 100000, ca. 30.000 Tokens), bekommt das Modell einen Fehler statt Teil-Daten und muss enger abfragen. Der Systemprompt hält es an, nur wenig zu laden (Zeitraum-Filter, zählen statt Listen).

## Skills

Anleitungen mit getesteten Shopware-Abfragen, die das Modell bei passender Frage selbst lädt (`view_skill`). Liegen in `skills/<id>/SKILL.md` und werden von `setup.py` bei jedem `up` angelegt bzw. aktualisiert, für alle Benutzer.

| Skill | Wofür |
|-------|-------|
| `bestellungen-suchen` | Bestellungen nach Produkt, Zeitraum, Status, Kunde, Firma, Nummer |
| `umsatz-auswertung` | Umsatz, Anzahl, Durchschnitt pro Tag/Woche/Monat, Top-Produkte |
| `stammkunden` | Kunden mit mehreren Bestellungen, Umsatz pro Kunde |
| `bestellstatus` | Bestell-, Zahlungs-, Lieferstatus, Tracking, unversandte Bestellungen |
| `produkte-lager` | Produktsuche, Preis, Bestand, niedriger Lagerbestand |
| `vorjahresvergleich` | Zeitraum gegen gleichen Zeitraum im Vorjahr |
| `shop-suche` | Spezialitäten geschenkkoerbe.ch: Kanäle (Galaxus, Pfister), Custom Fields, Konfigurator-Körbe, Lieferanten-Präfixe, Dokumente |

Neuer Skill: Ordner `skills/<id>/` mit `SKILL.md` anlegen (Frontmatter `name` und `description`, die Beschreibung entscheidet, wann das Modell ihn lädt), dann `docker compose --env-file .env.<instanz> up -d setup`. Gelöschte Ordner werden nicht automatisch entfernt (Admin → Workspace → Skills).

## Daten

Volume `shopware-chat-<APP_ENV>_data` (Chats, Benutzer). Neu anfangen: Container stoppen und Volume löschen.
