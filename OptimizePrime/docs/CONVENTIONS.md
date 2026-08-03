# CONVENTIONS — how we write SQL here

> **Summary:** Judgment calls a linter cannot enforce. Sort keys are dimension-first then time;
> aggregates are always state combinators, never raw distinct counts in a rollup; every table declares
> why its ordering key is what it is; tunables live in one place. Anything mechanically checkable
> belongs in a script, not here.

## Naming
- Tables: `snake_case`, singular subject + grain — `cc_minute_delta`, `session_intervals`.
- Views: `v_` prefix. Materialized views: `mv_` prefix, named after what they FILL.
- Columns: `snake_case`. State columns end `_state` (`active_state`).

## Table design
- **Every `CREATE TABLE` carries a comment saying why the ORDER BY is what it is.** If you cannot
  write that sentence, you have not chosen a key — you have guessed one.
- Sort key order: **filter dimensions first, time last**. Dashboards filter then scan a range.
- Truncated time in the key (`toStartOfMinute`), raw timestamp only at the tail. A coarse bucket
  prunes well because it repeats; a raw `DateTime64(3)` does not.
- `PRIMARY KEY` may be **shorter** than `ORDER BY` — keep the unique id in the sort order for dedup,
  out of the sparse index to keep it small.
- `LowCardinality(String)` for every dimension. `Decimal`, never `Float`, for anything money-like.
- Set `min_bytes_for_wide_part = 0` on tables we report compression for (Compact parts report 0).

## Aggregation
- **Never sum a distinct count across buckets.** `AggregatingMergeTree` + `uniqState`/`uniqMerge`, and
  `-MergeState` for a second hop. A `SummingMergeTree` over `uniqExact` over-counted **9×** in testing.
- A plain column in an `AggregatingMergeTree` that is neither in the sort key nor an aggregate is
  rejected on 26.7 — use `SimpleAggregateFunction(sum, …)`.
- Cascading MVs land in `AggregatingMergeTree`, never in a `SummingMergeTree`.

## Tunables
All model thresholds (`HEARTBEAT_GAP_S`, `TAIL_GRACE_S`, watermark) live at the top of
`sql/10_intervals.sql` and nowhere else. Changing one must not require a grep.

## Queries
- Select columns, never `SELECT *`, in anything that ships.
- Label benchmark runs with `SETTINGS log_comment='...'` so evidence is findable.
- Prefer `dictGet` over joining a small dimension.


## Delta / running-sum queries

- **The running sum over `cc_minute_delta` MUST `PARTITION BY toStartOfHour(minute)`.** Deltas are
  hour-clipped (ADR 0003) so each hour is absolute and standalone. Omitting the partition produces
  numbers that look plausible and are wrong, which is the worst failure mode we have.
- **Never insert into `cc_minute_delta` without truncating first.** It is an AggregatingMergeTree of
  sums with no dedup: a replayed batch silently doubles every number. Use `tools/build-model.sh`.
- Deltas ARE summable across dimensions; **peak is not**. One interval carries one dimension tuple,
  so summing deltas cannot double count a session — but `max()` of two dimensions' peaks is not the
  peak of their union.
- A delta view emits a row only where concurrency **changes**, so a range query must densify at read
  time; densifying in the view would defeat the delta model. **Fill the DELTA with zero, then take the
  running sum — never fill the LEVEL.** See below: this doc used to recommend the other way round.

### Densifying a delta range — the only correct recipe

```sql
SELECT minute,
       toInt64(sum(d) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
FROM (
    SELECT minute, sum(delta) AS d
    FROM cc_minute_delta
    WHERE minute >= {lo:DateTime} AND minute < {hi:DateTime}
    GROUP BY minute
    ORDER BY minute WITH FILL FROM {lo:DateTime} TO {hi:DateTime} STEP toIntervalSecond(60)
)
ORDER BY minute
```

Three things are load-bearing:

- **`WITH FILL` runs on the DELTA, inside the subquery.** `d` is not in the `ORDER BY`, so a filled
  row gets the default `0` — a minute where nothing changed contributes nothing, which is exactly
  what a delta means. The running sum then carries the level across it.
- **The running sum is `PARTITION BY toStartOfHour(minute)`,** applied *after* the fill, so every
  hour restarts at zero as ADR 0003 requires.
- **`FROM` / `TO` are explicit and must be literals or query parameters** (ClickHouse rejects a
  non-constant `FILL FROM`, including a scalar subquery). Without them the spine only spans the
  minutes that happen to have rows, so an empty leading or trailing stretch silently disappears.

**Do NOT** use `WITH FILL … INTERPOLATE (concurrent AS concurrent)` on the level. It is what this doc
recommended until ADR 0031 and it **invents viewers**: `INTERPOLATE` carries the last level forward
with no notion of the hour partition, so a level left non-zero at an hour boundary bleeds into an
hour that opened empty. Deltas are hour-clipped, and 40_deltas.sql deliberately does not emit a close
when an interval ends in the hour's last minute (the hour boundary already closes it) — so a
trailing non-zero level is normal, not a bug, and the naive densify turns it into phantom viewers.
Measured over the full delivered file: naive **10 wrong minutes, 10 phantom viewer-minutes** (all of
2026-07-24 13:00–13:09, served as 1 where truth is 0); corrected recipe **0 and 0**. Hour clipping is
what makes a 13-day range cost the same as one day; this is its sharp edge.

`sql/90_reconcile.sql` computes its `served` column the equivalent way — a dense spine `LEFT JOIN`ed
to the delta rows, then an hour-partitioned running sum. Either shape is fine; interpolating the
level is not.
