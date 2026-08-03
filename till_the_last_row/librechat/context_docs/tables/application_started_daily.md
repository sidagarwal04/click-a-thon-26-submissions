---
type: table
title: application_started_daily
description: Daily rollup of application_started (SharedAggregatingMergeTree), fed by mv_application_started_daily. Serves application_started_count and back_filled_rate directly from aggregate state.
kind: rollup
source_spec: specs/10_application_started/spec.md
source_schema: Atlys/schemas/10_application_started.sql
source_metrics: Atlys/schemas/10_application_started.metrics.json
live: true
timestamp: 2026-08-05
tags: [table, rollup, aggregating, live]
---

# Purpose

Pre-aggregated daily counts of `application_started` events, so single-event metrics
(`application_started_count`, `back_filled_rate`) are served without scanning the base table. Fed
by the materialized view `atlys.mv_application_started_daily`, which reads
`atlys.application_started` filtered to `payload.event = 'application_started'`.

# Engine & keys

- Engine: `SharedAggregatingMergeTree`.
- `ORDER BY (day, destination, purpose, flow, eta_shown, citizenship, is_back_filled)` — the seven
  grouping dimensions, all in the sort key.
- `PARTITION BY toYYYYMM(day)` (monthly).
- `TTL toDateTime(agg_insert_time) + toIntervalDay(90)` with `ttl_only_drop_parts = 1`
  — **D2**: TTL anchored on the rollup's own MATERIALIZED `agg_insert_time`, independent of the
  base table's `ch_insert_time`.

# Columns

| column | type | notes |
|---|---|---|
| day | Date | `toDate(payload.timestamp)` |
| destination | LowCardinality(String) | grouping dim |
| purpose | LowCardinality(String) | grouping dim |
| flow | LowCardinality(String) | grouping dim |
| eta_shown | LowCardinality(String) | grouping dim |
| citizenship | LowCardinality(String) | grouping dim |
| is_back_filled | Bool | grouping dim |
| applications | AggregateFunction(count) | `countState()` — total applications |
| unique_users | AggregateFunction(uniq, String) | `uniqState(user_id)` — distinct users |
| agg_insert_time | DateTime64(3,'UTC') MATERIALIZED now64(3) | TTL anchor (D2) |

# Reading aggregate state

Use `-Merge` combinators:

```sql
SELECT day, destination,
       countMerge(applications) AS applications,
       uniqMerge(unique_users)  AS unique_users
FROM atlys.application_started_daily
GROUP BY day, destination
```

# Notes / caveats

- The MV **only** materializes counts/uniques by the seven dims above. Any metric needing another
  slice (e.g. `co_travelers`, `device_type`, `os`) or another event must go to the **base table**
  or a cross-event join — not this rollup.
- `applications` (event count) ≠ `unique_users` (distinct `user_id`); a user can start several
  applications.

# Related

- Tables: [application_started](/tables/application_started.md)
- Metrics: [application-started-count](/metrics/application-started-count.md), [back-filled-rate](/metrics/back-filled-rate.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md) (os not a rollup dim; slice at base table)
- Source: `Atlys/schemas/10_application_started.sql` (`application_started_daily` + `mv_application_started_daily`), live `atlys` schema.
