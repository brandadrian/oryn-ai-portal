---
name: Produkte und Lager
description: Produkte suchen mit Preis, Bestand und Status, sowie Produkte mit niedrigem oder negativem Lagerbestand auflisten.
---

# Produkte und Lager

## Produkt suchen

Freitextsuche über `term` (Name, Produktnummer):

```json
{"entity":"product","criteria":{
  "limit":10,
  "term":"Nusstorte",
  "includes":{"product":["productNumber","name","stock","availableStock","price","active"]}}}
```

`price[0].gross` ist der Bruttopreis in CHF. `availableStock` = Bestand minus offene Bestellungen.

Varianten haben oft keinen eigenen Namen (`name` leer), dann gilt der Name des Hauptprodukts (`parentId`).

## Niedriger Bestand

Aktive Produkte mit Bestand bis 5, aufsteigend:

```json
{"entity":"product","criteria":{
  "limit":50,
  "filter":[
    {"type":"equals","field":"active","value":true},
    {"type":"range","field":"stock","parameters":{"lte":5}},
    {"type":"not","operator":"or","queries":[{"type":"contains","field":"name","value":"Geschenksverpackung"}]}],
  "sort":[{"field":"stock","order":"ASC"}],
  "includes":{"product":["productNumber","name","stock","availableStock"]}}}
```

## Hinweise

- Verpackungen ("Geschenksverpackung …") haben oft stark negativen Bestand, weil der Bestand nicht gepflegt wird. Deshalb im Beispiel ausgeschlossen. Wenn der Benutzer sie sehen will, Filter weglassen.
- Nur die Anzahl: `"limit":1`, `"total-count-mode":1`, `total` verwenden.
- Preise oder Bestand ändern nur auf ausdrücklichen Wunsch und nach Rückfrage (Tool `product_update`).
