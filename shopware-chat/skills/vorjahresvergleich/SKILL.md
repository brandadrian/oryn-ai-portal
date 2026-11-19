---
name: Vorjahresvergleich
description: Einen Zeitraum mit dem gleichen Zeitraum im Vorjahr vergleichen (Umsatz, Bestellungen, Durchschnitt, Top-Produkte), z.B. Weihnachtsgeschäft oder "bisher diesen Monat".
---

# Vorjahresvergleich

Zwei gleich aufgebaute Abfragen, nur das Datum verschoben. Gleich lange Zeiträume vergleichen: "bisher im November" heißt 1.–18.11. dieses Jahr gegen 1.–18.11. Vorjahr, nicht gegen den ganzen Vorjahresmonat.

## Abfrage (einmal pro Jahr)

```json
{"entity":"order","criteria":{
  "limit":1,
  "filter":[{"type":"range","field":"orderDateTime","parameters":{"gte":"2025-11-01T00:00:00","lt":"2025-11-19T00:00:00"}}],
  "includes":{"order":["orderNumber"]},
  "aggregations":[
    {"name":"umsatz","type":"sum","field":"amountTotal"},
    {"name":"schnitt","type":"avg","field":"amountTotal"}]}}
```

`total` = Anzahl Bestellungen.

Für Top-Produkte im Vergleich die Abfrage aus dem Skill "Umsatz-Auswertung" (order_line_item, terms auf label) für beide Zeiträume verwenden.

## Ausgabe

Kurze Tabelle mit Spalten Vorjahr, dieses Jahr, Veränderung in %:

| | 1.–18.11.2025 | 1.–18.11.2026 | Δ |
|---|---|---|---|
| Umsatz CHF | … | … | … % |
| Bestellungen | … | … | … % |
| Ø Bestellwert CHF | … | … | … % |

Veränderung = (dieses Jahr − Vorjahr) / Vorjahr × 100, auf eine Nachkommastelle. Danach ein bis zwei Sätze Einordnung, ohne zu spekulieren.
