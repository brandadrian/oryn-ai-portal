---
name: Shop-Suche geschenkkoerbe.ch
description: Spezialitäten von geschenkkoerbe.ch beim Suchen von Produkten und Bestellungen - Bestellkanäle (Galaxus, Pfister, Webshop), Custom Fields wie Wunschlieferdatum und Galaxus-Nummer, Konfigurator-Körbe, Lieferanten-Präfixe, Dokumenttypen. Laden, sobald eine Frage Kanal, Lieferdatum, Lieferant, Korb-Konfiguration oder Grusskarten betrifft.
---

# Shop-Suche geschenkkoerbe.ch (nur lesen)

- **Nur lesen.** Keine `*_create`, `*_update`, `*_delete`, `upload_media_by_url`, `theme_config_change`.
- Suchen mit `shopware_search` (volle DAL-Filter: `equals`, `equalsAny`, `contains`, `prefix`, `range`, `not`, `multi`).
- Custom Fields filtern mit `customFields.<name>`. Unklares Feld zuerst mit `fetch_single_entity_schema` prüfen.
- Was hier nicht steht, ist nicht geprüft. Nachfragen statt raten.

"Geprüft" = am 18.11.2026 per Abfrage im Live-Shop bestätigt.

## Bestellkanal (`order.affiliateCode`)

| Kanal | Wert | Stand im Shop |
|---|---|---|
| Webshop | `""` (leerer String, nicht null) | geprüft, Großteil der Bestellungen |
| Galaxus | `galaxus` | geprüft, aktiv (mehrere hundert pro Monat) |
| Pfister | `pfister` | geprüft, bisher nur sehr wenige Bestellungen |
| Galaxus Direktlieferung (neues Plugin) | Config `WaebGalaxusDirectDeliveryPlugin.config.affiliateCode`, Default `galaxus-direct` | im Shop noch keine Bestellung damit |

Filter: `{"type":"equals","field":"affiliateCode","value":"galaxus"}`. Webshop: `{"type":"equals","field":"affiliateCode","value":""}`.

Verteilung nach Kanal: Aggregation `{"name":"kanal","type":"terms","field":"affiliateCode","limit":10}`.

## Custom Fields an der Bestellung (`order.customFields`)

| Feld | Inhalt | Stand |
|---|---|---|
| `waeb_delivery_date_picker_delivery_date` | Wunschlieferdatum (`YYYY-MM-DD`) | geprüft, mit `range` filterbar |
| `cbaxExternalOrderOrdernumber` | Galaxus-Bestellnummer (aktueller Import) | geprüft, bei `affiliateCode = galaxus` |
| `cbaxExternalOrderCarrier` | Versanddienstleister des Galaxus-Imports (z.B. SwissPost) | geprüft |
| `waeb_galaxus_order_id` | Galaxus-Bestellnummer (neues Direktlieferungs-Plugin) | im Shop noch nicht befüllt |
| `waeb_pfister_order_id` | Pfister-Bestellnummer | nicht geprüft |

Beispiele:
- Galaxus-Nummer: `{"type":"equals","field":"customFields.cbaxExternalOrderOrdernumber","value":"123456789"}`
- Wunschlieferdatum ab 20.11.: `{"type":"range","field":"customFields.waeb_delivery_date_picker_delivery_date","parameters":{"gte":"2026-11-20"}}`

Bei `includes` mit `customFields` kommen viele lange Felder mit (z.B. Checkout-Texte). Nur ausgeben, was gefragt ist.

## Line Items (`order_line_item`)

Typen im Shop (geprüft): `product`, `customized-products`, `customized-products-option`, `option-values`, `custom`, `configurator-product`, `promotion`.

- **Konfigurator-Korb:** `type` = `configurator-product`.
  - Die Konfiguration liegt am Line Item in `customFields.configuratorProduct`, als JSON-String. Suche darin nur mit `contains`.
  - Kinder hängen über `parentId` am Korb: `customized-products` (Vorlage), `customized-products-option` (z.B. Grusstext als Textarea), `product` (Produkte im Korb).
- **Tracking pro Produkt:** `customFields.waeb_tracking_code`.
- Alle Positionen einer Bestellung: Filter `orderId` (oder `order.orderNumber`), danach `parentId` auswerten.

## Produkte (`product.productNumber`)

Präfixe der Lieferanten-Direktlieferungen (Default `Core.config.noPrintProductNumberPrefixes` = `GK-, M-, C-`):

| Präfix | Lieferant |
|---|---|
| `GK-` | Erny |
| `M-` | Marchon |
| `C-` | Jamei |

Ohne diese Präfixe: eigenes Produkt. Filter: `{"type":"prefix","field":"productNumber","value":"GK-"}`.

## Dokumente (`document.documentType.technicalName`)

Im Shop vorhanden (geprüft): `delivery_note`, `invoice`, `waeb_greeting_card` (Grusskarte).
Laut Code zusätzlich möglich, im Shop bisher nicht vorhanden: `delivery_note_erny`, `delivery_note_galaxus`.
