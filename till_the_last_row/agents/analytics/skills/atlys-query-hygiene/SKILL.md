---
name: atlys-query-hygiene
description: Token-safe, ClickHouse-idiomatic SQL discipline for the Atlys analytics agent — always compute aggregates in ClickHouse and return small result sets, never raw rows. Apply on every query the agent writes.
always-apply: true
---

# Skill: Query Hygiene (token-safe, ClickHouse-idiomatic)

The single most important discipline: **compute in ClickHouse, return small aggregates**.
Judges mark down agents that stream raw rows into the LLM.

## Never
- `SELECT *` without a tight `LIMIT` for exploration only (and even then LIMIT 5).
- Returning per-user or per-event rows to reason over in the LLM.
- Doing arithmetic/averages/counts in the LLM that SQL should do.
- Running unbounded scans without a `timestamp` filter when a window is implied.

## Always
- Aggregate: `uniqExact`, `uniq`, `count`, `countIf`, `sum`, `avg`, `quantile(0.5)(...)`.
- `GROUP BY` the segment(s); `ORDER BY` the metric; `LIMIT` top-N (e.g. 25).
- Add volume columns so small segments can be judged (`uniqExact(user_id) AS users`).
- Filter time windows explicitly.
- Round rates (`round(x, 4)`) for readable output.

## Handling the messy data in SQL (not in your head)
```sql
-- FLAT tables (the 8 legacy raw tables):
lower(coalesce(nullIf(device_type,''),'unknown')) AS device_norm
coalesce(nullIf(os,''), if(lower(device_type)='android','android','unknown')) AS os_norm
-- exclude backfill / dupes for live behaviour:
WHERE (is_back_filled = 0 OR is_back_filled IS NULL)
  AND (duplicate_id = '' OR duplicate_id IS NULL)
```
For **JSON `payload`** tables (new instrumented specs) the same cleaning wraps `payload.*`:
```sql
lower(coalesce(nullIf(toString(payload.device_type),''),'unknown')) AS device_norm
coalesce(nullIf(toString(payload.os),''), if(lower(toString(payload.device_type))='android','android','unknown')) AS os_norm
```
Detect the shape with `DESCRIBE` first (see `atlys-json-payload-access`): flat = plain
columns; JSON = a `payload JSON(...)` column accessed via `payload.<field>` (backtick-escape
nested paths, `CAST` before math/GROUP BY).

## Useful ClickHouse functions for this dataset
- `windowFunnel(window_secs)(timestamp, cond1, cond2, ...)` — ordered funnels.
- `sequenceMatch('(?1)(?2)')(timestamp, cond1, cond2)` — ordered pattern checks.
- `uniqExact(user_id)` — distinct users per stage/segment.
- `toDate(timestamp)`, `toStartOfWeek(timestamp)` — trends.
- `quantiles(0.5,0.9)(retry_count)` — capture-quality distributions.
- `argMax`, `any` — pick a representative attribute per group.

## Introspection (cheap, do this before guessing columns)
```sql
DESCRIBE TABLE atlys.<table>;   -- also reveals shape: flat columns vs a `payload JSON(...)` column
SELECT name, type FROM system.columns WHERE database='atlys' AND table='<table>';
-- time window: flat tables use `timestamp`; JSON tables use `payload.timestamp`
SELECT count(), min(timestamp), max(timestamp) FROM atlys.<flat_table>;
SELECT count(), min(payload.timestamp), max(payload.timestamp) FROM atlys.<json_table>;
-- prefer a pre-aggregated MV sibling if one exists (read with *Merge combinators):
SELECT name FROM system.tables WHERE database='atlys' AND name LIKE '%_agg';
```

## Result-size self-check before every query
Ask: "How many rows will this return?" If it's not a small aggregate (roughly <= a few
dozen rows), add grouping/limits. Read back numbers, then narrate.
