---
name: Bestell- und Versandstatus
description: Zu einer Bestellnummer Bestellstatus, Zahlungsstatus, Lieferstatus, Versandart, Lieferdatum und Tracking-Nummer anzeigen, oder offene bzw. unversandte Bestellungen auflisten.
---

# Bestell- und Versandstatus

## Status einer Bestellung

```json
{"entity":"order","criteria":{
  "limit":1,
  "filter":[{"type":"equals","field":"orderNumber","value":"40012345"}],
  "associations":{
    "stateMachineState":{},
    "transactions":{"associations":{"stateMachineState":{}}},
    "deliveries":{"associations":{"stateMachineState":{},"shippingMethod":{}}}},
  "includes":{
    "order":["orderNumber","orderDateTime","amountTotal","stateMachineState","transactions","deliveries"],
    "state_machine_state":["technicalName","name"],
    "order_transaction":["stateMachineState"],
    "order_delivery":["stateMachineState","trackingCodes","shippingDateEarliest","shippingDateLatest","shippingMethod"],
    "shipping_method":["name"]}}}
```

## Status auf Deutsch

| technicalName | Bestellung | Zahlung | Lieferung |
|---------------|-----------|---------|-----------|
| open | offen | offen | nicht versandt |
| in_progress | in Bearbeitung | | |
| completed | abgeschlossen | | |
| cancelled | storniert | storniert | storniert |
| paid | | bezahlt | |
| paid_partially | | teilweise bezahlt | |
| refunded | | erstattet | |
| shipped | | | versandt |
| shipped_partially | | | teilweise versandt |
| returned | | | retourniert |

Tracking-Nummern stehen in `deliveries[].trackingCodes`. Gibt es keine, sagen, dass noch keine Sendungsnummer hinterlegt ist.

## Liste: bezahlt, aber noch nicht versandt

```json
{"entity":"order","criteria":{
  "limit":100,
  "filter":[
    {"type":"equals","field":"transactions.stateMachineState.technicalName","value":"paid"},
    {"type":"equals","field":"deliveries.stateMachineState.technicalName","value":"open"},
    {"type":"range","field":"orderDateTime","parameters":{"gte":"2026-11-01T00:00:00"}}],
  "includes":{"order":["orderNumber","orderDateTime","amountTotal"]},
  "sort":[{"field":"orderDateTime","order":"ASC"}]}}
```

Status nur lesen. Status ändern nur, wenn der Benutzer es ausdrücklich verlangt, und vorher nachfragen.
