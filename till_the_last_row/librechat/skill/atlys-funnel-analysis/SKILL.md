---
name: atlys-funnel-analysis
description: Use when analyzing the Atlys 4-step conversion funnel (destination_card_clicked -> application_started -> document_uploaded -> purchase_completed), computing drop-off, step-through, or conversion rate. Provides correct windowFunnel/uniqExact ClickHouse patterns.
---

# Skill: Funnel Analysis

Goal: compute the 4-step conversion funnel and drop-off correctly, in ClickHouse,
returning only aggregates.

Funnel order: `destination_card_clicked` -> `application_started` ->
`document_uploaded` -> `purchase_completed`.

## Rules
- Count **distinct users** (`uniqExact(user_id)`) reaching each stage, in `timestamp`
  order, within a time window. Past `application_started`, `application_id` is a valid
  grain too.
- Prefer `windowFunnel()` / `sequenceMatch()` over dumping rows and counting in the LLM.
- Always apply a time window (`WHERE timestamp >= ... AND timestamp < ...`).
- Consider excluding `is_back_filled = 1` for live-behaviour reads; state your choice.

## Pattern A — stage counts (simple, robust)
```sql
SELECT
    countDistinctIf(user_id, stage = 'card')  AS s1_card,
    countDistinctIf(user_id, stage = 'app')   AS s2_app,
    countDistinctIf(user_id, stage = 'doc')   AS s3_doc,
    countDistinctIf(user_id, stage = 'buy')   AS s4_buy
FROM
(
    SELECT user_id, 'card' AS stage FROM atlys.destination_card_clicked WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
    UNION ALL SELECT user_id, 'app' FROM atlys.application_started      WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
    UNION ALL SELECT user_id, 'doc' FROM atlys.document_uploaded        WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
    UNION ALL SELECT user_id, 'buy' FROM atlys.purchase_completed       WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
);
```
Then derive step-through and drop-off from the four numbers.

## Pattern B — windowFunnel (ordered per user, e.g. within 7 days)
```sql
SELECT
    level,
    count() AS users
FROM
(
    SELECT
        user_id,
        windowFunnel(604800)(timestamp,
            event = 'card', event = 'app', event = 'doc', event = 'buy') AS level
    FROM
    (
        SELECT user_id, timestamp, 'card' AS event FROM atlys.destination_card_clicked
        UNION ALL SELECT user_id, timestamp, 'app' FROM atlys.application_started
        UNION ALL SELECT user_id, timestamp, 'doc' FROM atlys.document_uploaded
        UNION ALL SELECT user_id, timestamp, 'buy' FROM atlys.purchase_completed
    )
    WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
    GROUP BY user_id
)
GROUP BY level
ORDER BY level;
```
`level >= k` = users who reached stage k. Drop-off between k and k+1 =
`1 - (users at level>=k+1) / (users at level>=k)`.

## Pattern C — JSON `payload` table (a single instrumented spec, stages = `payload.event`)
A new spec is ONE table whose stages are event-type values in `payload.event` — no
cross-table UNION needed. `windowFunnel` reads them directly (see `atlys-json-payload-access`):
```sql
SELECT level, count() AS users
FROM
(
    SELECT
        payload.user_id AS user_id,
        -- windowFunnel rejects DateTime64 — wrap the typed path in toDateTime(...)
        windowFunnel(604800)(toDateTime(payload.timestamp),
            payload.event = 'express_checkout_shown',
            payload.event = 'express_payment_confirmed') AS level
    FROM atlys.express_checkout
    WHERE payload.timestamp >= {start:DateTime} AND payload.timestamp < {end:DateTime}
    GROUP BY user_id
)
GROUP BY level ORDER BY level;
```
For simple stage counts on a JSON table use `countDistinctIf(payload.user_id, payload.event =
'<stage>')`. If the spec ships a funnel `*_agg` MV, read that with `countMerge` instead of
scanning the raw table.

## Segmented funnel
Add the segment to the inner projection and `GROUP BY user_id, <segment>`, then
aggregate by segment. On JSON tables the segment is `toString(payload.<dim>)`. Always run
at least device + geo cuts before concluding (see the `atlys-segment-comparison` skill).

## Conversion denominator
Per the `atlys-data-dictionary` skill, contradiction #2: within-funnel conversion uses
`application_started` as denominator. State this explicitly. Do NOT silently use
"sessions" unless asked for the leadership headline (then approximate via
`uniqExact(app_session_id)` and flag it).
