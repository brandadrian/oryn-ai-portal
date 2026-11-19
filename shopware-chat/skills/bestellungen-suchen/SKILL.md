---
name: Bestellungen suchen
description: Bestellungen finden nach Produkt, Zeitraum, Status, Kunde, Firma oder Bestellnummer, z.B. "alle Bestellungen mit Nusstorte der letzten 30 Tage".
---

# Bestellungen suchen

Immer **eine** Abfrage mit `shopware_search` auf `entity: "order"`. Keine Bestellungen einzeln mit `order_detail` öffnen.

## Regeln

- Zeitraum immer als `range` auf `orderDateTime` mit konkretem Datum (heute ist im Systemprompt), Ende exklusiv mit `lt`.
- Produkt: `contains` auf `lineItems.label` (Teil des Namens reicht, z.B. "Nusstorte").
- `includes` nur mit den nötigen Feldern, `sort` nach `orderDateTime` absteigend.
- `limit` 100. Ist `total` größer als die Anzahl geladener Einträge, das dem Benutzer sagen und nach engerem Zeitraum fragen oder Seite 2 laden (`"page": 2`).
- Antwort als kurze Tabelle: Bestellnummer, Datum, Betrag (CHF), bei Bedarf Kunde.

## Beispiel: Bestellungen mit einem Produkt in einem Zeitraum

```json
{"entity":"order","criteria":{
  "limit":100,
  "filter":[
    {"type":"range","field":"orderDateTime","parameters":{"gte":"2026-10-19T00:00:00","lt":"2026-11-19T00:00:00"}},
    {"type":"contains","field":"lineItems.label","value":"Nusstorte"}],
  "includes":{"order":["orderNumber","orderDateTime","amountTotal"]},
  "sort":[{"field":"orderDateTime","order":"DESC"}]}}
```

## Weitere Filter

| Frage | Filter |
|-------|--------|
| Bestellnummer | `{"type":"equals","field":"orderNumber","value":"40012345"}` |
| Kunde (E-Mail) | `{"type":"contains","field":"orderCustomer.email","value":"muster"}` |
| Kunde (Name) | `{"type":"contains","field":"orderCustomer.lastName","value":"Muster"}` |
| Firma | `{"type":"contains","field":"orderCustomer.company","value":"Muster AG"}` |
| Nur Firmenkunden | `{"type":"not","operator":"and","queries":[{"type":"equals","field":"orderCustomer.company","value":null}]}` |
| Bezahlt | `{"type":"equals","field":"transactions.stateMachineState.technicalName","value":"paid"}` |
| Noch nicht versandt | `{"type":"equals","field":"deliveries.stateMachineState.technicalName","value":"open"}` |
| Betrag ab 500 CHF | `{"type":"range","field":"amountTotal","parameters":{"gte":500}}` |

Für den Kunden in der Ausgabe: `"includes":{"order":["orderNumber","orderDateTime","amountTotal","orderCustomer"],"order_customer":["firstName","lastName","company","email"]}`.

Nur die Anzahl gefragt: `"limit":1` und `total` aus der Antwort nehmen.
