---
type: table
title: group_family_daily
description: Pre-aggregated daily rollup of group_family — distinct groups started/submitted and traveller add/remove/docs-incomplete counts by day × destination × group_size. Fed by group_family_daily_mv. Live in ClickHouse.
kind: aggregate
source_schema: Atlys/schemas/02_group_family.sql
source_metrics: Atlys/schemas/02_group_family.metrics.json
live: true
timestamp: 2026-08-07
tags: [table, aggregate, rollup, group, family, live]
---

# Purpose

`SharedAggregatingMergeTree` daily rollup of [group_family](/tables/group_family.md). Serves all
four group-family PM metrics without scanning the base table. Fed incrementally by the
`atlys.group_family_daily_mv` MATERIALIZED VIEW. Live with **754 rows**.

# Grain (ORDER BY)

`event_date × destination × group_size`

- `event_date` `Date` = `toDate(payload.timestamp)` (**event time**, not ingest time).
- `destination` `LowCardinality(String)`, `group_size` `UInt8`.
- **PARTITION BY** `toYYYYMM(event_date)`.

# Aggregate states

| column | state (agg table) | measure | finalizer |
|---|---|---|---|
| groups_started | `AggregateFunction(uniq, String)` | distinct `group_id` with `group_started` | `uniqMerge(groups_started)` |
| groups_submitted | `AggregateFunction(uniq, String)` | distinct `group_id` with `group_submitted` | `uniqMerge(groups_submitted)` |
| travellers_added_cnt | `AggregateFunction(sum, UInt64)` | count of `traveller_added` | `sumMerge(travellers_added_cnt)` |
| travellers_removed_cnt | `AggregateFunction(sum, UInt64)` | count of `traveller_removed` | `sumMerge(travellers_removed_cnt)` |
| docs_incomplete_cnt | `AggregateFunction(sum, UInt64)` | `traveller_added` rows with `docs_complete = false` | `sumMerge(docs_incomplete_cnt)` |
| docs_added_cnt | `AggregateFunction(sum, UInt64)` | count of `traveller_added` (docs-share denominator) | `sumMerge(docs_added_cnt)` |

MV source expressions (`FROM atlys.group_family GROUP BY event_date, destination, group_size`):

```sql
uniqIfState(CAST(payload.group_id,'String'), payload.event = 'group_started')   AS groups_started
uniqIfState(CAST(payload.group_id,'String'), payload.event = 'group_submitted') AS groups_submitted
sumState(toUInt64(payload.event = 'traveller_added'))                            AS travellers_added_cnt
sumState(toUInt64(payload.event = 'traveller_removed'))                          AS travellers_removed_cnt
sumState(toUInt64(payload.event = 'traveller_added' AND payload.docs_complete = false)) AS docs_incomplete_cnt
sumState(toUInt64(payload.event = 'traveller_added'))                            AS docs_added_cnt
```

> ⚠️ The MV columns are typed `AggregateFunction(uniqIf, String, UInt8)` for the group counts,
> while the destination agg table declares them `AggregateFunction(uniq, String)`. This is the
> standard `uniqIfState` → `uniqMerge` pattern: the `If` combinator makes the conditional part of
> the state, and the merge target reads it as a `uniq` state. See D4.

# Deviations

- **D2** — TTL is `event_date + 90 day`, `ttl_only_drop_parts = 1` — keyed on the **derived event
  date** because this agg has **no insert-watermark column** (unlike the base table's
  `ch_insert_time`). Analytics note: agg rows age out by event date, so very old events roll off
  even if only recently ingested. Contrast [group_family](/tables/group_family.md) base TTL.
- **D4** — group counts use `uniqIfState(CAST(group_id,'String'), <event predicate>)` so the
  `AggregateFunction(uniq, ...)` state stays **non-nullable**. Writing it as `uniqState(...)` with
  a row-level `WHERE` would either drop rows needed by other measures or produce nullable states;
  the `If` combinator keeps one scan feeding all six measures.

# Serves

- [group-completion-rate](/metrics/group-completion-rate.md) — `uniqMerge(groups_submitted) / uniqMerge(groups_started)` by `group_size`.
- [traveller-churn](/metrics/traveller-churn.md) — `sumMerge(travellers_removed_cnt) / sumMerge(travellers_added_cnt)`.
- [docs-incomplete-share](/metrics/docs-incomplete-share.md) — `sumMerge(docs_incomplete_cnt) / sumMerge(docs_added_cnt)`.
- [group-apps-by-destination](/metrics/group-apps-by-destination.md) — `uniqMerge(groups_started)` grouped by `destination`.

# Related

- Base table: [group_family](/tables/group_family.md)
- Entities: [event](/entities/event.md), [destination](/entities/destination.md)
- Contradictions: [group-id-untyped-metric-unit](/contradictions/group-id-untyped-metric-unit.md)
- Source: `Atlys/schemas/02_group_family.sql`, live `atlys` schema (`group_family_daily`, `group_family_daily_mv`)
