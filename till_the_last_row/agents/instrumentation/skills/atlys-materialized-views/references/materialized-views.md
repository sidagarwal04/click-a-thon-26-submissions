# Materialized Views Reference (single base table, `payload` JSON column)

Only generate MVs when the **Step 2d derivation** (NDJSON profile + Q3 `common_metrics` +
`spec.md` questions) concludes an MV is justified — see SKILL.md Step 2d. Do **NOT** generate
MVs by default.

All MVs read from the **single base table** for the spec (there is one table per spec, not one
per event type). The base table stores each event object in a single `JSON` column named
`payload`, so the MV `SELECT` reads dimensions and metrics through `payload.*` paths:
`payload.event`, `payload.destination`, `payload.timestamp`, `payload.\`payment.latency_ms\``,
etc. Cast paths to concrete types in the SELECT.

When a metric or dimension applies to only **some** event types (e.g. `payment.*` exists only
on `express_payment_confirmed`), add `WHERE payload.event = '<event_type>'` to the MV so it
aggregates only the relevant rows.

## When an MV is warranted (recap of Step 2d)

| spec.md / Q3 question pattern | MV worth generating? |
|---|---|
| "hourly/daily counts per {dimension}" | ✅ Yes — count MV |
| "p95 latency grouped by {dimension}" | ✅ Yes — quantile MV |
| "conversion/funnel/attach rate sliced by X" | ✅ Yes — count/ratio MV |
| "show the raw events / look up one record" | ❌ No — query the base table directly |

---

## Incremental vs. refreshable — ALWAYS prefer incremental

**Default: incremental `AggregatingMergeTree` MVs that fire on insert.** This is the correct
and most performant choice for a growing event table.

- An incremental MV aggregates only the **newly inserted block** into partial aggregate states.
  It **never rescans the base table** — cost scales with insert size, not table size.
- `toStartOfDay` / `toStartOfHour` is only the **bucket granularity**, not a refresh cadence.
  A daily-bucketed incremental MV still updates continuously as rows arrive. You do **not**
  need a refreshable MV to get hourly/daily rollups.

Use a **refreshable MV** (`REFRESH EVERY 1 HOUR ... AS SELECT ...`) **only** when the
aggregation genuinely cannot be expressed incrementally:

| Needs refreshable MV | Why incremental can't do it |
|---|---|
| JOINs across tables | insert block only sees new rows of one table |
| dedup / `argMax` / "latest state per key" over full history | needs to see all rows, not just the new block |
| top-N / `LIMIT` / window functions | require a global view of the data |
| any metric that must rescan the whole base table | not derivable from per-block partial states |

None of the standard funnel-count / latency-quantile / sum metrics need this — keep them
incremental.

---

## Steps

1. Identify bucket granularity (hourly, daily) from the request — this is `toStartOf*`, **not**
   a refresh schedule.
2. Identify dimension paths (the GROUP BY fields) on the `payload` column.
3. Decide whether to filter by `payload.event` (metric applies to some event types only).
4. Map aggregate functions (see table below).
5. Generate two objects per MV: the AggregatingMergeTree backing table + the MV.

## Aggregate function mapping

| Goal | ClickHouse aggregate state |
|---|---|
| Row count | `countState()` → `AggregateFunction(count)` |
| Average | `avgState(x)` → `AggregateFunction(avg, Float64)` |
| p50/p95/p99 | `quantileState(0.95)(x)` → `AggregateFunction(quantile(0.95), {type})` (one per quantile) |
| Distinct count | `uniqState(x)` → `AggregateFunction(uniq, String)` |
| Sum | `sumState(x)` → `AggregateFunction(sum, Float64)` |

## Two-object pattern per MV

### 1. AggregatingMergeTree backing table

```sql
CREATE TABLE IF NOT EXISTS atlys.{mv_backing_table}
(
    day          Date,
    {dim1}       LowCardinality(String),
    {dim2}       LowCardinality(String),
    {metric1}    AggregateFunction({agg_func}, {type}),
    -- Compute/ingestion-time watermark. TTL is keyed on THIS, never on `day`.
    agg_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY ({dim1}, {dim2}, day)
TTL toDateTime(agg_insert_time) + INTERVAL {ttl_days} DAY DELETE
SETTINGS ttl_only_drop_parts = 1;
```

> ORDER BY fields on the backing table must be NOT NULL. Since JSON paths can be absent,
> wrap dimensions in `COALESCE(CAST(payload.{dim} AS String), '')` in the MV SELECT and
> declare them as `String` / `LowCardinality(String)` (not `Nullable`) in the backing table.

> **TTL keys on `agg_insert_time` (compute time), NOT on `day` (event date).** If the TTL
> were `day + INTERVAL N DAY`, any backfilled or recomputed historical rollup would land
> with a `day` already older than the server-clock cutoff and be **silently TTL-deleted on
> the next merge** the moment it's written. Keying on `agg_insert_time` (a `MATERIALIZED
> now64(3)` watermark, mirroring the base table's `ch_insert_time`) measures retention from
> when the rollup was produced, so backfilled history survives its full window. `agg_insert_time`
> is `MATERIALIZED`, so it is NOT written by the MV SELECT — the column list of the MV is
> unchanged.

### 2. Materialized View (reads `payload.*` from the single base table)

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.{mv_name}
TO atlys.{mv_backing_table}
AS SELECT
    toDate(payload.{timestamp_path})                          AS day,
    COALESCE(CAST(payload.{dim1} AS String), '')              AS {dim1},
    COALESCE(CAST(payload.{dim2} AS String), '')              AS {dim2},
    {agg_func}State(CAST(payload.`{metric_path}` AS {type}))  AS {metric1}
FROM atlys.{spec_table}
-- add WHERE payload.event = '{event_type}' when the metric is event-type-specific
GROUP BY day, {dim1}, {dim2};
```

---

## Real example 1: `destination_daily_funnel_agg` (all event types, no filter)

Daily funnel counts per `destination` + `geoip_country_code`, keeping `event_type` so the
funnel stages are queryable — reads the discriminator straight from the single base table.

```sql
CREATE TABLE IF NOT EXISTS atlys.destination_daily_funnel_agg
(
    day                Date,
    event_type         LowCardinality(String),
    destination        LowCardinality(String),
    geoip_country_code LowCardinality(String),
    event_count        AggregateFunction(count),
    agg_insert_time    DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (destination, geoip_country_code, event_type, day)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.destination_daily_funnel_mv
TO atlys.destination_daily_funnel_agg
AS SELECT
    toDate(payload.timestamp)                                AS day,
    COALESCE(CAST(payload.event AS String), '')              AS event_type,
    COALESCE(CAST(payload.destination AS String), '')        AS destination,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    countState()                                             AS event_count
FROM atlys.express_checkout
GROUP BY day, event_type, destination, geoip_country_code;

-- Query example (funnel per destination for a day)
SELECT event_type, destination, countMerge(event_count) AS n
FROM atlys.destination_daily_funnel_agg
WHERE day = today()
GROUP BY event_type, destination
ORDER BY destination, n DESC;
```

## Real example 2: `payment_latency_daily_agg` (single event type — uses WHERE filter)

p95 latency + sum(amount) per `destination`, only for `express_payment_confirmed` rows
(the `payment.*` paths exist only on that event type).

```sql
CREATE TABLE IF NOT EXISTS atlys.payment_latency_daily_agg
(
    day                Date,
    destination        LowCardinality(String),
    geoip_country_code LowCardinality(String),
    latency_p95        AggregateFunction(quantile(0.95), UInt32),
    total_amount       AggregateFunction(sum, Float64),
    payment_count      AggregateFunction(count),
    agg_insert_time    DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (destination, geoip_country_code, day)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.payment_latency_daily_mv
TO atlys.payment_latency_daily_agg
AS SELECT
    toDate(payload.timestamp)                                AS day,
    COALESCE(CAST(payload.destination AS String), '')        AS destination,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    quantileState(0.95)(CAST(payload.`payment.latency_ms` AS UInt32)) AS latency_p95,
    sumState(CAST(payload.`payment.amount` AS Float64))      AS total_amount,
    countState()                                             AS payment_count
FROM atlys.express_checkout
WHERE payload.event = 'express_payment_confirmed'
GROUP BY day, destination, geoip_country_code;

-- Query example
SELECT destination,
       quantileMerge(0.95)(latency_p95) AS p95_ms,
       sumMerge(total_amount)           AS revenue,
       countMerge(payment_count)        AS payments
FROM atlys.payment_latency_daily_agg
GROUP BY destination
ORDER BY payments DESC;
```

---

## String-literal rule (most common generation bug)

Every string literal and type modifier uses **single quotes only**:
`'UTC'`, `DateTime64(3, 'UTC')`, `'express_payment_confirmed'`, `'express_checkout_shown' AS event_type`.

**Never** wrap a literal in escaped double quotes — this is invalid ClickHouse SQL, and chdb
will reject it:

```sql
-- ❌ WRONG (do not generate):
'"express_checkout_shown"' AS event_type
DateTime64(3, '"UTC"')
```

## Casting metric paths

Cast JSON metric paths **directly**; do not stringify first. Prefer
`CAST(payload.\`payment.latency_ms\` AS UInt32)` over
`toUInt32OrZero(toString(payload.\`payment.latency_ms\`))`. Use the `...OrZero` forms only if a
path is known to contain non-numeric junk, and always confirm the chosen form passes chdb.

> ClickHouse Cloud does not need a `Distributed` wrapper — query the backing table directly.
> Incremental MVs fire on **insert**, aggregating each new block into partial states — they do
> not rescan the base table and do not run on a schedule.
