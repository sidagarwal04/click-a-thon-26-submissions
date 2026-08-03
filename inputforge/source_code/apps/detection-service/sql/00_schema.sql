-- Full schema for the incremental (append-only, hour-at-a-time) pipeline.
-- Run once via `npm run setup:local` (or before first deploy). Consolidates
-- what used to be spread across the old batch pipeline's 01_schema.sql +
-- 05_zr_series.sql's CREATE TABLE, plus the new tables the incremental
-- rewrite needed (metric_noise_baseline) — see sql/incremental/README.md
-- for the full per-table rationale.

-- Raw source tables — `IF NOT EXISTS` deliberately, since these are meant
-- to be loaded (INSERT'd into) separately from this repo, not owned by it.
-- Matches the authoritative DDL at
-- click-a-thon-2026/InMobi/data/ddl.sql exactly (column names, order,
-- types, and ad_events' PARTITION BY toDate(event_time)) — if a real
-- loader creates these first with a different shape, `IF NOT EXISTS`
-- means these definitions are silently skipped in favor of whatever's
-- already there, which is the safe direction for this to fail in.
CREATE TABLE IF NOT EXISTS inmobi.ad_events (
  event_time     DateTime64(3),
  app_id         String,
  geo_device_id  String,
  advertiser_id  String,                      -- empty string on unfilled requests
  ad_format      LowCardinality(String),       -- banner | interstitial | native | rewarded | video
  is_filled      UInt8,
  is_impression  UInt8,
  is_click       UInt8,
  revenue        Float64
) ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (event_time, app_id);

CREATE TABLE IF NOT EXISTS inmobi.apps (
  app_id         String,
  category       LowCardinality(String),       -- gaming | social | entertainment | news | ecommerce | utility | finance
  publisher_tier LowCardinality(String)        -- tier_1 | tier_2 | tier_3
) ENGINE = MergeTree ORDER BY app_id;

CREATE TABLE IF NOT EXISTS inmobi.advertisers (
  advertiser_id  String,
  vertical       LowCardinality(String),       -- gaming | ecommerce | finance | travel | entertainment | auto | cpg
  campaign_type  LowCardinality(String)        -- CPM | CPC | CPI
) ENGINE = MergeTree ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS inmobi.geo_device (
  geo_device_id  String,
  region         LowCardinality(String),       -- NAM | EU | APAC | LATAM | MEA
  country        LowCardinality(String),
  device_model   LowCardinality(String),
  os_version     LowCardinality(String)
) ENGINE = MergeTree ORDER BY geo_device_id;

-- SummingMergeTree, not plain MergeTree: this table is now fed by
-- mv_metrics_hourly (sql/mv/01_mv_metrics_hourly.sql), a materialized view
-- triggered on every INSERT into inmobi.ad_events, not a hand-rolled hourly
-- cron. A block of raw events can land partially-within an hour (or span
-- several hours in one bulk load), so more than one partial row per
-- (hour_ts,d,dow,hod) is expected and normal here — SummingMergeTree folds
-- them together on merge. Never read this table directly for a "one row per
-- hour" assumption; always go through inmobi.metrics_hourly_v below, which
-- re-aggregates defensively regardless of merge state.
CREATE TABLE IF NOT EXISTS inmobi.metrics_hourly (
  hour_ts   DateTime,
  d         Date,
  dow       UInt8,   -- 1=Mon .. 7=Sun (toDayOfWeek)
  hod       UInt8,   -- 0..23
  requests  UInt64,
  fills     UInt64,
  impressions UInt64,
  clicks    UInt64,
  revenue   Float64
) ENGINE = SummingMergeTree ORDER BY (hour_ts, d, dow, hod);

-- The only safe way to read metrics_hourly — GROUP BY re-sums partial rows
-- regardless of whether a background merge has folded them yet. Every query
-- that used to read inmobi.metrics_hourly directly (zr, proportion, the
-- daily noise baseline, the analyst view) reads this instead.
CREATE VIEW IF NOT EXISTS inmobi.metrics_hourly_v AS
SELECT hour_ts, d, dow, hod,
  sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions,
  sum(clicks) AS clicks, sum(revenue) AS revenue
FROM inmobi.metrics_hourly
GROUP BY hour_ts, d, dow, hod;

-- Plain MergeTree, not Replacing: mv_zr_hourly (sql/mv/02) is a REFRESHABLE
-- MV now, not a reactive one — it recomputes the full series and atomically
-- REPLACEs this table's content every cycle, so there's exactly one writer
-- and nothing to dedupe. `computed_at` is informational (when the row was
-- last (re)computed), not a ReplacingMergeTree version column. Do not use
-- FINAL here — ClickHouse Cloud's SharedMergeTree rejects FINAL outright on
-- a non-Replacing table (ILLEGAL_FINAL), it doesn't silently no-op.
CREATE TABLE IF NOT EXISTS inmobi.metric_zr_hourly (
  metric      LowCardinality(String),
  hour_ts     DateTime,
  d           Date,
  dow         UInt8,
  hod         UInt8,
  zr          Float64,
  computed_at DateTime DEFAULT now()
) ENGINE = MergeTree ORDER BY (metric, hour_ts);

-- Plain MergeTree, not Replacing: mv_detect_global (sql/mv/03) is this
-- table's only writer, a refreshable MV that recomputes every currently-
-- qualifying anomaly across full history and atomically REPLACEs this
-- table's content every cycle — same reasoning as metric_zr_hourly above.
-- This means the table always reflects what qualifies under the CURRENT
-- detection_config, not whatever config was active when an hour first got
-- scored; that's an intentional property of the refresh-and-replace design,
-- not a side effect. Do not use FINAL — see metric_zr_hourly's comment.
CREATE TABLE IF NOT EXISTS inmobi.anomalies (
  detected_at DateTime DEFAULT now(),
  metric      LowCardinality(String),   -- requests | revenue | fill_rate | render_rate | ctr | ecpm | rpr
  method      LowCardinality(String),   -- trend_seasonal | proportion | day_level
  time_window DateTime,                 -- start of the flagged hour (hour_ts)
  observed    Nullable(Float64),
  expected    Nullable(Float64),
  delta       Nullable(Float64),        -- observed - expected
  pct_delta   Nullable(Float64),        -- delta / expected (null for methods that don't report it)
  z           Float64,
  baseline_n  Nullable(UInt16)          -- observations used for the baseline/model fit
) ENGINE = MergeTree ORDER BY (metric, method, time_window);

-- trend_seasonal only persists its standardized residual; it deliberately
-- has no raw observed/expected pair. Keep those columns nullable, including
-- when upgrading an older environment whose original table made them strict.
ALTER TABLE inmobi.anomalies MODIFY COLUMN observed Nullable(Float64);
ALTER TABLE inmobi.anomalies MODIFY COLUMN expected Nullable(Float64);
ALTER TABLE inmobi.anomalies MODIFY COLUMN delta Nullable(Float64);
ALTER TABLE inmobi.anomalies MODIFY COLUMN baseline_n Nullable(UInt16);

CREATE TABLE IF NOT EXISTS inmobi.detection_config (
  metric      LowCardinality(String),
  method      LowCardinality(String),   -- trend_seasonal | proportion | day_level
  z_threshold Float64,
  enabled     UInt8 DEFAULT 1,
  incident_enabled UInt8 DEFAULT 1      -- 0 = retain as evidence, never open/page an incident
) ENGINE = MergeTree ORDER BY (metric, method);
ALTER TABLE inmobi.detection_config
  ADD COLUMN IF NOT EXISTS incident_enabled UInt8 DEFAULT 1;
-- The one piece of the pipeline that's genuinely live-editable without a
-- redeploy — every tick reads this fresh. See sql/01_detection_config_seed.sql
-- for the current (InMobi's own recall-first defaults, NOT independently
-- validated — see README's threshold-validation note) values.

-- Canonical reportable incidents. This is the target of the refreshable
-- mv_incidents view (sql/mv/12): incident formation needs the full anomaly
-- history, so it cannot be implemented correctly as an INSERT-triggered MV.
-- The refresh replaces this table atomically every ten minutes.
CREATE TABLE IF NOT EXISTS inmobi.incidents (
  metric        LowCardinality(String),
  start_time    DateTime,
  end_time      DateTime,
  span_hours    UInt16,
  flagged_hours UInt16,
  methods       Array(String),
  max_abs_z     Float64,
  detected_at   DateTime,
  observed      Nullable(Float64),
  expected      Nullable(Float64),
  pct_delta     Nullable(Float64),
  refreshed_at  DateTime
) ENGINE = MergeTree ORDER BY (metric, start_time);

-- metric_noise_baseline: the pooled residual variance per metric, used to
-- shrink trend_seasonal's per-cell variance. A slow-moving property of a
-- metric's overall noise level — refreshed daily by
-- sql/incremental/02_noise_baseline_daily.sql, read via argMax (latest row
-- per metric) by every hourly tick that needs it.
CREATE TABLE IF NOT EXISTS inmobi.metric_noise_baseline (
  metric      LowCardinality(String),
  pooled_var  Float64,
  computed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(computed_at) ORDER BY metric;

-- cusum and ewma_fast/ewma_slow (and their state tables, cusum_state /
-- metric_seasonal_ewma_state) have been removed entirely — cusum was a true
-- sequential recurrence that a block-triggered MV can't fold correctly under
-- a bulk multi-hour load, and ewma's variance estimate was never validatable
-- on this dataset's history. If either state table still exists in a given
-- environment from before this cleanup, drop it manually
-- (`DROP TABLE IF EXISTS inmobi.cusum_state` /
-- `DROP TABLE IF EXISTS inmobi.metric_seasonal_ewma_state`) — this file no
-- longer recreates or references them.
