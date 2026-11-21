---
name: MySQL-Abfragen Shopware
description: Lesende SQL-Abfragen auf die Shopware-Datenbanken (production, staging) mit dem MySQL-Tool. Laden bei Fragen zu Bestellungen, Kunden, Produkten oder Daten, die direkt in der Datenbank nachgeschaut werden sollen.
---

# MySQL-Abfragen (nur lesen)

Tools: `umgebungen`, `tabellen_auflisten`, `tabelle_beschreiben`, `sql_abfrage` (die Verbindung gehört fest zur Umgebung des Modells, PROD oder STAGING; Parameter `umgebung` leer lassen). Erlaubt sind nur SELECT, WITH, SHOW, DESCRIBE, EXPLAIN; max. 500 Zeilen, 30 s.

## Shopware-Besonderheiten

- IDs sind `binary(16)`: ausgeben mit `HEX(id)`, vergleichen mit `UNHEX('…')`.
- Viele Tabellen sind versioniert: nur Live-Daten mit `version_id = UNHEX('0fa91ce3e96a4bc2be4bd9ce752c3425')`.
- `order` ist ein reserviertes Wort: immer `` `order` `` schreiben.
- Texte (Namen) stehen in `*_translation`-Tabellen, z. B. `product_translation.name`.

## Wichtige Tabellen

`order` (order_number, order_date_time, amount_total), `order_line_item` (order_id, label, quantity), `order_customer` (order_id, email, first_name, last_name), `order_delivery`, `order_transaction`, `state_machine_state` (technical_name), `product` (product_number, stock, active), `product_translation`, `customer`.

Unklare Spalten zuerst mit `tabelle_beschreiben` prüfen.

## Beispiele

```sql
-- Bestellungen der letzten 7 Tage
SELECT order_number, order_date_time, amount_total FROM `order`
WHERE version_id = UNHEX('0fa91ce3e96a4bc2be4bd9ce752c3425') AND order_date_time >= NOW() - INTERVAL 7 DAY
ORDER BY order_date_time DESC LIMIT 50;

-- Positionen einer Bestellung
SELECT li.label, li.quantity, li.total_price FROM order_line_item li
JOIN `order` o ON o.id = li.order_id AND o.version_id = li.order_version_id
WHERE o.order_number = '40012345' AND o.version_id = UNHEX('0fa91ce3e96a4bc2be4bd9ce752c3425');

-- Produkte mit wenig Bestand
SELECT product_number, stock FROM product
WHERE version_id = UNHEX('0fa91ce3e96a4bc2be4bd9ce752c3425') AND active = 1 AND stock < 5 ORDER BY stock LIMIT 50;
```

## Regeln

- Immer `LIMIT` und nur benötigte Spalten; für Zahlen `COUNT`/`SUM` statt Listen.
- Nur die Datenbank der eigenen Umgebung ist erreichbar. Fragen zur anderen Umgebung an das entsprechende PROD- bzw. STAGING-Modell verweisen.
- Personendaten (E-Mail, Adresse) nur ausgeben, wenn ausdrücklich gefragt.
- Kommt ein Fehler „MySQL-Zugang fehlt“, ist der Lese-User noch nicht eingerichtet – das sagen, nicht raten.
