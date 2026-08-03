# The rollup layer

The pre-aggregation tier the detection sweep and drill-down read instead of the 9M-row fact
table. This is the piece that makes diagnosis time depend on the number of *distinct segment
values* rather than on the number of events, which is what has to hold when the unseen
incident dataset turns out to be larger than this sample.

Files: `clickhouse/rollups.sql` (the original 12) and `clickhouse/monitoring_rollups.sql`
(the 7 added for sub-hourly and composite scopes). Run order matters and is documented in
`CLAUDE.md`: `schema.sql` → `dictionaries.sql` → `rollups.sql` → `load.sql`.

## Why one narrow table per dimension, not one wide one

The obvious design — a single table keyed `(hour, app_id, geo_device_id, advertiser_id)` —
was considered and rejected on arithmetic. With 2,000 apps × 5,000 geo/device profiles × 500
advertisers, that cross-product has **more distinct combinations than there are rows in
`ad_events`**, so the "rollup" would be the same size as the fact table with none of the
locality. It would shrink nothing.

One narrow table per dimension instead. Each keeps 5–2,000 distinct values per hour, so each
is a small fraction of the raw table, and — the part that actually matters for the engine —
every dimension exposes the **same query shape**:

```sql
SELECT value, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue)
FROM   hourly_by_<dimension>
WHERE  hour >= {window_start} AND hour < {window_end}
GROUP BY value
```

One code path in `engine/sweep.py` ranks every dimension because the shape does not vary.
Adding a scope is adding a rollup, not adding a query.

## What exists, measured

| Table | Rows | Grain | Key beyond time |
|---|---:|---|---|
| `hourly_overall` | 840 | hour | — |
| `hourly_by_app` | 1,235,633 | hour | `app_id` (2,000) |
| `hourly_by_advertiser` | 408,773 | hour | `advertiser_id` (500 + `''`) |
| `hourly_by_format` | 4,200 | hour | `ad_format` (5) |
| `hourly_by_region` | 4,200 | hour | `region` (5) |
| `hourly_by_country` | 13,440 | hour | `country` (16) |
| `hourly_by_device_model` | 6,720 | hour | `device_model` (8) |
| `hourly_by_os_version` | 6,720 | hour | `os_version` (8) |
| `hourly_by_category` | 5,880 | hour | `category` (7) |
| `hourly_by_publisher_tier` | 2,520 | hour | `publisher_tier` (3) |
| `hourly_by_vertical` | 6,720 | hour | `vertical` (7 + `''`) |
| `hourly_by_campaign_type` | 3,360 | hour | `campaign_type` (3 + `''`) |
| `hourly_geo_cell` | 107,503 | hour | `region, country, device_model` |
| `hourly_os_family_region` | 8,400 | hour | `os_family, region` |
| `hourly_format_region` | 21,000 | hour | `ad_format, region` |
| `minute5_overall` | 10,080 | 5 min | — |
| `minute5_by_region` | 50,400 | 5 min | `region` |
| `minute5_by_format` | 50,400 | 5 min | `ad_format` |
| `reach_hourly` | 840 | hour | — (uniq states) |
| **total** | **1,947,629** | | vs 9,000,000 raw |

Two tables dominate: `hourly_by_app` and `hourly_by_advertiser` are 84% of all rollup rows,
because 2,000 apps × 840 hours is inherently large while `region` × 840 hours is 4,200. That
is the expected shape, not a defect — the point is that even the largest is 14% of the fact
table and is keyed so that a single dimension's scan touches one narrow table.

Only three of the 14 monitored grains have their own physical table (5 min, hour, and the
implicit day). The other eleven — 15m, 5h, 10h, 15h, 5d, 10d, 15d, 1w, 2w, 3w, 1mo — are
**rolling sums computed over these same tables** by RANGE-framed window functions in
`engine/baselines_job.py`. A separate table per grain would be 14× the storage for no new
information.

## Why only additive counters are stored

Every column is a plain sum: `requests`, `fills`, `impressions`, `clicks`, `revenue`. No
rates are stored, ever.

This is forced by `Docs/metrics_glossary.md`, which defines every ratio metric as **sum over
the group divided by sum over the group** — never an average of per-row or per-hour ratios.
If `hourly_by_region` stored a `fill_rate` column, then summing across hours would average
the ratios and produce a different number from the glossary's formula. The two disagree
whenever traffic is uneven across hours, which it always is (the data has real hour-of-day
seasonality). So the ratio is computed at read time from the two sums:

```sql
sum(fills) / sum(requests)          -- fill_rate, matching the glossary exactly
sum(revenue) / sum(impressions) * 1000  -- eCPM
```

Because everything is additive, `SummingMergeTree` is sufficient — no
`AggregatingMergeTree` or `-State` combinators. **Always wrap columns in `sum(...)`**:
`SummingMergeTree` collapses same-key rows only during background merges, so an unwrapped
`SELECT requests` can return several partial rows for one hour.

The one exception is `reach_hourly`, which stores `uniqState(...)` in an
`AggregatingMergeTree` because distinct-device and distinct-app counts are **not additive** —
you cannot sum two hours' unique-device counts to get the two-hour count. Query it with
`uniqMerge(uniq_devices)`. It is deliberately the only table that needs this.

## How the dimension key is derived

The dimension columns live on the three dimension tables, not on `ad_events`. Rather than
joining, the materialized views enrich each row through the in-memory dictionaries from
`dictionaries.sql`:

```sql
dictGet('apps_dict', 'category', tuple(app_id))            -- hourly_by_category
dictGet('geo_device_dict', 'region', tuple(geo_device_id))  -- hourly_by_region
```

A dictionary lookup is a hash probe against an in-memory structure, so the MV stays a
streaming per-block transform with no join stage. `os_family` in `hourly_os_family_region` is
derived from `os_version` by taking the token before the space (`'Android 15'` → `'Android'`),
which is why it is a rollup column rather than a dimension-table column.

### The `''` advertiser bucket

`advertiser_id` is **empty on unfilled requests** — no ad was served, so there is no
advertiser to attribute. This has three consequences the layer has to handle explicitly:

1. **Use `dictGetOrDefault`, not `dictGet`, for advertiser-derived fields.** `''` has no
   dictionary entry, and `dictGet` on a missing key returns the type's default silently. The
   `vertical` and `campaign_type` rollups therefore carry an explicit `''` bucket meaning
   "the request was never filled", which is a real and useful segment.
2. **`hourly_by_advertiser` keeps its `''` row.** Dropping it would break reconciliation:
   `sum(requests)` would no longer equal `count(*)` over `ad_events`, and the volume side of
   the revenue decomposition identity would be wrong.
3. **`fill_rate` and `rpr` are meaningless on advertiser-derived scopes.** Within
   `advertiser_id != ''` every row is filled by construction, so `fill_rate ≡ 1.0` — it is
   not a low-variance metric, it is an identity. Measured: 20,643 zero-spread bands before
   this was handled. `engine/scopes.py` marks these via
   `unsupported_metrics=("fill_rate", "rpr")` on the advertiser, vertical and campaign_type
   scopes, so they are never banded and never breach.

## Backfill rules

Materialized views in ClickHouse fire **only on rows inserted after the view exists**. They
are not retroactive. This is the single most common way to get a silently half-empty rollup.

- **The intended path** is the documented run order: create the MVs *before* `load.sql`, and
  the bulk insert into `ad_events` populates every rollup as a side effect, for free.
- **If the fact table is already loaded** (which is what happened here for `rollups.sql`, and
  again for all 7 tables in `monitoring_rollups.sql`), each rollup needs a one-time
  `INSERT INTO <rollup> SELECT <the MV's own SELECT body> FROM ad_events`.
- **Backfill is not idempotent.** `SummingMergeTree` adds, so running the same backfill twice
  doubles every counter — and it will still look internally consistent, because every metric
  doubles together and the *ratios* stay correct. Only a comparison against raw `ad_events`
  catches it, which is why reconciliation is not optional.
- `scripts/apply_monitoring.py` handles this per **day**: it compares each day's request count
  against raw, and for any day that disagrees it issues `ALTER TABLE … DELETE` for that day
  and re-inserts only that day. Repairing a partial backfill therefore does not require
  rebuilding the whole table, and re-running the script on a healthy table is a no-op.
- The script **exits non-zero on any surviving mismatch**, so a broken rollup fails the
  deploy rather than quietly serving wrong numbers into an investigation.

## Reconciliation

Every rollup must satisfy: its own totals equal the same aggregates computed from raw
`ad_events`. Nothing depends on a rollup until this passes.

```sql
-- raw baseline
SELECT count(*) AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, round(sum(revenue), 2) AS revenue
FROM ad_events;

-- any rollup, which must return identical numbers
SELECT sum(requests), sum(fills), sum(impressions), sum(clicks), round(sum(revenue), 2)
FROM hourly_by_region;
```

**Current state, measured across all 18 counter rollups:** every one matches raw `ad_events`
exactly on all five measures — `requests = 9,000,000`, `fills = 7,027,910`,
`impressions = 6,887,058`, `clicks = 74,940`, `revenue = 17,020.36`, with `req_delta = 0` and
`rev_delta = 0.00` in every case. (`reach_hourly` is excluded because uniq states are not
comparable by summation; check it with
`SELECT uniqMerge(uniq_devices) FROM reach_hourly` against
`SELECT uniq(geo_device_id) FROM ad_events`.)

Per-day reconciliation is the more useful form when hunting a partial backfill, because a
whole-table total can match while individual days are wrong in offsetting directions:

```sql
SELECT toDate(hour) AS d, sum(requests) AS rollup_requests
FROM hourly_overall GROUP BY d ORDER BY d;
-- against
SELECT toDate(event_time) AS d, count(*) AS raw_requests
FROM ad_events GROUP BY d ORDER BY d;
```

## Adding a dimension

1. Add a narrow `SummingMergeTree` table plus its MV to `clickhouse/monitoring_rollups.sql`,
   keyed `(hour, <the new column>)`, columns limited to the five additive counters.
2. **Check the cardinality first.** The rule from the top of this document applies to every
   addition: if `distinct values × hours` approaches the fact table's row count, the rollup
   buys nothing. The three composite rollups here were each measured before being created
   (128, 10 and 25 combinations respectively) rather than assumed to be small.
3. Register the scope in `engine/scopes.py` — including `unsupported_metrics` if the key makes
   any metric an identity, per the `fill_rate` case above.
4. Run `scripts/apply_monitoring.py` to create and backfill it, and let its reconciliation
   check gate the result.

Never widen an existing rollup's key to cover a new dimension. A composite key's cardinality
is the product of its parts, and the whole design rests on keeping each table narrow.
