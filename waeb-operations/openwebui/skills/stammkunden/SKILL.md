---
name: Stammkunden
description: Kunden mit mehreren Bestellungen in einem Zeitraum finden, mit Anzahl Bestellungen, Umsatz und letzter Bestellung.
---

# Stammkunden

Eine `terms`-Aggregation pro Kunden-E-Mail, sortiert nach Anzahl, mit Limit. Nie alle Kunden laden.

## Top-Kunden im Zeitraum

Ohne Angabe des Benutzers: laufendes Jahr.

```json
{"entity":"order","criteria":{
  "limit":1,
  "filter":[{"type":"range","field":"orderDateTime","parameters":{"gte":"2026-01-01T00:00:00"}}],
  "includes":{"order":["orderNumber"]},
  "aggregations":[{"name":"kunden","type":"terms","field":"orderCustomer.email","limit":20,
    "sort":{"field":"_count","order":"DESC"},
    "aggregation":{"name":"umsatz","type":"sum","field":"amountTotal"}}]}}
```

Jeder Bucket: `key` = E-Mail, `count` = Bestellungen, `umsatz.sum` = Umsatz CHF.

Nach Umsatz statt Anzahl sortieren: `"sort":{"field":"umsatz","order":"DESC"}` geht nicht, stattdessen die Buckets selbst nach `umsatz.sum` ordnen.

## Details zu den Top-Kunden

Nur wenn gefragt (Name, Firma, letzte Bestellung): eine zweite Abfrage für die E-Mails der Top-Liste.

```json
{"entity":"order","criteria":{
  "limit":100,
  "filter":[{"type":"equalsAny","field":"orderCustomer.email","value":["mail@beispiel.ch","info@firma.ch"]}],
  "includes":{"order":["orderNumber","orderDateTime","orderCustomer"],"order_customer":["firstName","lastName","company","email"]},
  "sort":[{"field":"orderDateTime","order":"DESC"}]}}
```

## Hinweise

- E-Mails können sich in Groß-/Kleinschreibung unterscheiden (z.B. `Max.Muster@…` und `max.muster@…`), dann zusammenzählen und das erwähnen.
- Interne Adressen (z.B. `@geschenkkoerbe.ch`) sind meist Bestellungen des Shops selbst, als solche kennzeichnen.
- Als "Stammkunde" gilt ohne andere Vorgabe: mindestens 3 Bestellungen im Zeitraum.
