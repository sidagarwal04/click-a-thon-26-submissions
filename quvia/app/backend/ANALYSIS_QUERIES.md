# Analysis queries — the `py` database

These are the exact, verified queries this app's backend runs against
ClickHouse (see `backend/app/db.py`). LibreChat should run these same
queries — not improvise its own SQL, and never query any table named
`ad_events` in any database (`quvia_hack.ad_events`, `ganesh.ad_events`, or
`py.ad_events` — every database has a copy of the raw 9-million-row event
log, none of them power this dashboard) — so its answers match this
dashboard's numbers exactly.

## Why this database, and how it's shaped

`py` is a self-contained, more complete pipeline than the older `ganesh` one:
5 time granularities per dimension (1 minute, 5 minute, 1 hour, 6 hour,
1 day), and per-dimension anomaly tables at every granularity — not just an
overall one. It covers **9 dimensions** (not 11 — `py` has no `app_id` or
`advertiser_id` breakdown): `ad_format`, `campaign_type`, `category`,
`country`, `device_model`, `os_version`, `publisher_tier`, `region`,
`vertical`.

Every `agg_*` table is a plain `SharedSummingMergeTree` — read with a normal
`SELECT`/`GROUP BY`, no `Merge()` functions needed (unlike the old `ganesh`
`AggregatingMergeTree` tables).

**The baseline is a rolling average, not a fixed lookup table.** Instead of
a separate `baseline_1h`-style table with every hour-of-week slot
pre-computed, `py`'s own anomaly materialized views compute an *expanding
window* average/stddev live: for each `(segment, is-Sat-or-Sun, hour-of-day)`
slot, average every prior occurrence of that slot (`ROWS BETWEEN UNBOUNDED
PRECEDING AND 1 PRECEDING`). Two consequences:

1. It only requires **weekend-vs-weekday**, not the exact day of week (so
   Tuesday 3pm and Thursday 3pm share one baseline, unlike the old `ganesh`
   pipeline which kept all 7 days separate).
2. Because it's expanding-window, non-flagged hours don't have a
   pre-computed "expected" value stored anywhere — `anomaly_*_1h` tables
   only contain rows that already crossed the threshold. Query B and C below
   replicate the exact same window logic live to get an "expected" value for
   *every* hour/segment, not just the anomalous ones.

## Query A — is this hour actually abnormal, and what changed?

Reads directly from the anomaly table — already has z-scores and %-changes
for four metrics (requests, revenue, fill rate, eCPM), precomputed.

```sql
SELECT bucket, requests, avg_requests, z_requests, pct_requests,
       revenue, avg_revenue, z_revenue, pct_revenue,
       fill_rate, avg_fill_rate, z_fill_rate, pct_fill_rate,
       ecpm, avg_ecpm, z_ecpm, pct_ecpm
FROM py.anomaly_overall_1h
WHERE segment = 'all' AND bucket = {bucket}
-- flagged as a real anomaly if abs(z) > 3 AND the pct-change clears a
-- practical floor per metric (10% for requests/revenue, 2% for fill_rate/ecpm)
```

`py.anomaly_<dimension>_1h` (e.g. `py.anomaly_country_1h`) has the identical
shape, plus a `segment` column for the specific value (e.g. `'US'`).

## Query B — every category, ranked by who's most responsible

One dimension lives in one physical table (`py.agg_<dimension>_1h`) — there's
no single shared table across all 9 like `ganesh.dim_metrics_1h` was, so this
runs once per dimension and combines the results.

```sql
WITH stats AS (
    SELECT bucket, segment, revenue,
           row_number() OVER (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC) AS rn,
           avg(revenue) OVER w AS revenue_expected
    FROM py.agg_country_1h    -- swap for any of the 9 dimension tables
    WINDOW w AS (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT 'country' AS dimension_name, segment AS dimension_value, revenue, revenue_expected,
       (revenue - revenue_expected) AS delta
FROM stats
WHERE bucket = {bucket} AND rn > 4
```

Repeat for `py.agg_ad_format_1h`, `py.agg_campaign_type_1h`,
`py.agg_category_1h`, `py.agg_device_model_1h`, `py.agg_os_version_1h`,
`py.agg_publisher_tier_1h`, `py.agg_region_1h`, `py.agg_vertical_1h`
(swapping the dimension_name literal each time), `UNION ALL` them, then rank
**within each dimension_name separately** — pooling all 9 into one shared
total deflates every percentage and points at the wrong culprit. The
backend's actual implementation (`db.get_contribution`) builds this exact
UNION programmatically; see `db.py` for the full generated query.

## Query C — full day, hour by hour, actual vs. expected

Same rolling-window logic as Query B, applied to the overall (no-breakdown)
table, for every hour of one calendar day — this is what feeds the
dashboard's full-day trend line chart.

```sql
WITH stats AS (
    SELECT bucket, segment, revenue,
           row_number() OVER (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC) AS rn,
           avg(revenue) OVER w AS expected
    FROM py.agg_overall_1h
    WINDOW w AS (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT bucket, revenue, expected
FROM stats
WHERE toDate(bucket) = {date} AND segment = 'all' AND rn > 4
ORDER BY bucket
```

## The list of currently flagged anomalies

```sql
SELECT bucket, revenue, avg_revenue, pct_revenue, z_revenue,
       pct_requests, pct_fill_rate, pct_ecpm
FROM py.anomaly_overall_1h
WHERE segment = 'all'
ORDER BY abs(z_revenue) DESC
```

## Not yet used by this dashboard, but available in `py`

- **Finer granularities**: `1m` / `5m` / `6h` / `1d` versions of every table
  above exist (e.g. `py.agg_overall_1m`, `py.anomaly_country_5m`) — a natural
  path to true minute-level drill-down without ever touching the raw
  `ad_events` table.
- **`py.funnel_violations_1h` / `_1d`**: counts of logically-impossible
  events — a click with no impression, a click with no fill, an impression
  with no fill. A data-quality signal `ganesh` doesn't have at all.
