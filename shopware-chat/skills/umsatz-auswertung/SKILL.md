---
name: Umsatz-Auswertung
description: Umsatz, Anzahl Bestellungen und Durchschnitt pro Tag, Woche oder Monat sowie die meistverkauften Produkte in einem Zeitraum.
---

# Umsatz-Auswertung

Zahlen immer mit `aggregations` von Shopware rechnen lassen, nie Bestelllisten laden und selbst summieren. `"limit":1` setzen, die Anzahl Bestellungen steht in `total`.

## Umsatz im Zeitraum, aufgeteilt pro Tag

`interval`: `day`, `week`, `month` oder `year`.

```json
{"entity":"order","criteria":{
  "limit":1,
  "filter":[{"type":"range","field":"orderDateTime","parameters":{"gte":"2026-11-01T00:00:00","lt":"2026-12-01T00:00:00"}}],
  "includes":{"order":["orderNumber"]},
  "aggregations":[
    {"name":"umsatz","type":"sum","field":"amountTotal"},
    {"name":"schnitt","type":"avg","field":"amountTotal"},
    {"name":"verlauf","type":"histogram","field":"orderDateTime","interval":"day",
     "aggregation":{"name":"umsatz","type":"sum","field":"amountTotal"}}]}}
```

Jeder Bucket in `verlauf` hat `key` (Datum), `count` (Bestellungen) und `umsatz.sum`.

## Meistverkaufte Produkte

Auf `order_line_item`, nur Produkte (`type = product`), Zeitraum über `order.orderDateTime`:

```json
{"entity":"order_line_item","criteria":{
  "limit":1,
  "filter":[
    {"type":"range","field":"order.orderDateTime","parameters":{"gte":"2026-11-01T00:00:00","lt":"2026-12-01T00:00:00"}},
    {"type":"equals","field":"type","value":"product"}],
  "includes":{"order_line_item":["label"]},
  "aggregations":[{"name":"top","type":"terms","field":"label","limit":10,
    "sort":{"field":"_count","order":"DESC"},
    "aggregation":{"name":"menge","type":"sum","field":"quantity"}}]}}
```

`count` = Anzahl Bestellpositionen, `menge.sum` = verkaufte Stück.

## Hinweise

- `amountTotal` ist brutto in CHF, inkl. Versand.
- Umsatz nur bezahlter Bestellungen: Filter `{"type":"equals","field":"transactions.stateMachineState.technicalName","value":"paid"}` ergänzen und das dazusagen.
- Ergebnis kurz: Gesamtumsatz, Anzahl, Durchschnitt, danach Tabelle. Zeitraum immer nennen.
