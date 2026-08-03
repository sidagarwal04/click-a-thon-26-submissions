---
name: atlys-json-payload-access
description: "How to query the two table shapes in the Atlys `atlys` database — the 8 legacy raw tables have FLAT columns, while every newly instrumented spec is ONE table with a single JSON column named `payload`. Detect the shape with DESCRIBE first, then use the right accessor — flat columns directly, or typed paths like `payload.event` and backtick-escaped nested paths like ``payload.`payment.latency_ms` `` with an explicit CAST. Apply on every query so column access and casts are correct."
always-apply: true
---

# Skill: JSON Payload Access (two table shapes)

The `atlys` database contains **two shapes**. Never assume — `DESCRIBE` first, then pick the
accessor.

| Shape | Which tables | How fields are stored |
|---|---|---|
| **Flat** (legacy) | the 8 raw funnel/supporting tables (`destination_card_clicked`, `application_started`, `document_uploaded`, `purchase_completed`, `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`) | one column per field: `device_type`, `timestamp`, `value`, … |
| **JSON payload** (new) | every table produced by the Instrumentation Agent (one base table per spec) | a single `JSON` column named `payload`; all event types share it; event-type discriminator at `payload.event` |

## Detect the shape (cheap, do this before writing field access)

```sql
DESCRIBE TABLE atlys.<table>;
-- Flat  → many typed columns, no `payload`.
-- JSON  → a `payload` column of type `JSON(...)` (+ `ch_insert_time`).
```

If you see a `payload JSON(...)` column, use the JSON-access rules below. Otherwise use flat
column names (see `atlys-data-dictionary`).

## Accessing a JSON `payload` table

### Top-level paths — `payload.<field>`
```sql
payload.event                 -- event-type discriminator (LowCardinality String)
payload.user_id               -- String
payload.application_id        -- LowCardinality(String)
payload.destination
payload.timestamp             -- the event's own time (DateTime64(3,'UTC'))
payload.geoip_country_code
```

### Nested paths — backtick-escape the dotted key
A nested field like `{"payment": {"latency_ms": 320}}` is the path `payment.latency_ms`. Write
the **whole dotted path inside one pair of backticks** after `payload.`:
```sql
payload.`payment.latency_ms`
payload.`payment.amount`
```
`payload.payment.latency_ms` (no backticks) is **wrong** and will not resolve.

### Always CAST typed-hint-absent paths in aggregates/filters
Only the ORDER BY/PARTITION paths carry a type hint. Everything else comes back as a dynamic
JSON value — **cast it** to the concrete type you need before math or grouping:
```sql
CAST(payload.`payment.latency_ms` AS UInt32)
CAST(payload.`payment.amount`     AS Float64)
toString(payload.destination)                       -- for grouping/normalizing strings
COALESCE(CAST(payload.destination AS String), '')   -- guard NULL/absent for GROUP BY keys
```
Use `...OrZero` / `...OrNull` forms (`toUInt32OrZero(toString(...))`) only if a path is known to
contain non-numeric junk; otherwise a direct `CAST` is cleaner and faster.

### Gotcha: `windowFunnel` needs `DateTime`, not `DateTime64`
`payload.timestamp` carries the typed hint `DateTime64(3,'UTC')`, which `windowFunnel` rejects
(`Illegal type DateTime64 ... must be Unsigned Number, Date, DateTime`). Wrap it:
```sql
windowFunnel(604800)(toDateTime(payload.timestamp), payload.event = 's1', payload.event = 's2')
```
Plain comparisons, `toDate()`, and `min/max` on `payload.timestamp` work without the wrap.

### Filter by event type (one table holds all event types)
Because a spec's events all live in one table, scope to the event type you mean:
```sql
WHERE payload.event = 'express_payment_confirmed'
```
A field like `payment.*` exists only on some event types — filter first, then aggregate.

## Prefer the MV backing tables when they exist

Instrumented specs ship incremental `AggregatingMergeTree` MVs (e.g. `destination_click_daily_agg`
for spec `08_destination_card_clicked`). Those are **flat** aggregate-state tables — read them with
the `...Merge` combinators instead of scanning the raw `payload` table. The state columns match the
MV's `...State` producers; `DESCRIBE` the agg table to see the exact `AggregateFunction(...)` types:
```sql
-- real shape (08): destination_click_daily_agg
SELECT destination,
       countMerge(clicks)        AS clicks,        -- from countState()
       sumMerge(guest_clicks)    AS guest_clicks,  -- from sumState(...)
       uniqMerge(unique_users)   AS unique_users   -- from uniqState(...)
FROM atlys.destination_click_daily_agg
WHERE day >= {start:Date} AND day < {end:Date}     -- `day` is the event date (grouping key)
GROUP BY destination;
```
Match the `*Merge` combinator to the state's producer: `countState`→`countMerge`,
`sumState`→`sumMerge`, `uniqState`→`uniqMerge`, `quantileState(q)`→`quantileMerge(q)`,
`avgState`→`avgMerge`. Check `system.tables` for a `*_agg` sibling before hand-aggregating the raw
JSON table.

### `agg_insert_time` is operational, not an analysis dimension
Agg tables carry an `agg_insert_time DateTime64(3,'UTC')` column. It is the **row's ingestion/compute
time**, used only to anchor the retention TTL (rollups are dropped 90 days after they were *computed*,
not after the event date — so back-filled history is not silently TTL-deleted). **Do NOT** use
`agg_insert_time` as the time axis for trends or windows — the event date is the `day` grouping key.
`agg_insert_time` is not present on the raw `payload` base table.

## Worked contrast (same metric, two shapes)

Flat table:
```sql
SELECT lower(device_type) AS device, avg(value) AS avg_value
FROM atlys.purchase_completed
WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
GROUP BY device;
```

JSON payload table:
```sql
SELECT toString(payload.device_type) AS device,
       avg(CAST(payload.`payment.amount` AS Float64)) AS avg_amount
FROM atlys.express_checkout
WHERE payload.event = 'express_payment_confirmed'
  AND payload.timestamp >= {start:DateTime} AND payload.timestamp < {end:DateTime}
GROUP BY device;
```

## Rules
- **Always** `DESCRIBE` an unfamiliar table to pick flat vs JSON access before writing field refs.
- For JSON tables, filter/segment/order via `payload.*`; backtick-escape nested dotted keys; CAST
  before math or GROUP BY; guard NULL/absent with `COALESCE`.
- Scope to `payload.event` when a metric applies to only some event types.
- Prefer a `*_agg` MV (with `...Merge`) over scanning the raw JSON table when one exists.
- Still return only small aggregates — the shape does not change the token-safety rule
  (`atlys-query-hygiene`).
