-- Segment-level detection schema. Global sweeps (01-06) can miss an incident
-- that's real and severe in one segment but cancels out in the aggregate —
-- e.g. two ad_formats moving opposite directions in eCPM, net ~0 globally.
-- This mirrors the global tables one level deeper: (dimension, segment) added
-- to every grouping/partition key, same shrinkage/z-score math throughout.

-- SummingMergeTree, not plain MergeTree: fed by mv_segment_metrics_hourly
-- (sql/mv/07), a reactive materialized view triggered on every INSERT into
-- inmobi.ad_events — same reasoning as inmobi.metrics_hourly (see
-- ../00_schema.sql's comment on it). More than one partial row per
-- (dimension,segment,hour_ts) is expected and normal; never read this
-- directly for a "one row per cell" assumption, always go through
-- inmobi.segment_metrics_hourly_v below.
CREATE TABLE IF NOT EXISTS inmobi.segment_metrics_hourly (
  hour_ts   DateTime,
  d         Date,
  dow       UInt8,
  hod       UInt8,
  dimension LowCardinality(String), -- ad_format | category | publisher_tier | region | country | vertical | campaign_type
  segment   LowCardinality(String), -- e.g. 'banner', 'gaming', 'tier_1', 'NAM', 'US', 'finance', 'CPM'
  requests  UInt64,   -- for vertical/campaign_type this is filled-event count, not true top-of-funnel requests — see sql/mv/07_mv_segment_metrics_hourly.sql
  fills     UInt64,
  impressions UInt64,
  clicks    UInt64,
  revenue   Float64
) ENGINE = SummingMergeTree ORDER BY (dimension, segment, hour_ts, d, dow, hod);

-- The only safe way to read segment_metrics_hourly — GROUP BY re-sums
-- partial rows regardless of merge state. Every query that used to read
-- inmobi.segment_metrics_hourly directly reads this instead.
CREATE VIEW IF NOT EXISTS inmobi.segment_metrics_hourly_v AS
SELECT hour_ts, d, dow, hod, dimension, segment,
  sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions,
  sum(clicks) AS clicks, sum(revenue) AS revenue
FROM inmobi.segment_metrics_hourly
GROUP BY hour_ts, d, dow, hod, dimension, segment;

-- Plain MergeTree, not Replacing: mv_segment_detect_global (sql/mv/08) is
-- this table's only writer, a refreshable MV that atomically REPLACEs its
-- content every cycle — same reasoning as inmobi.anomalies
-- (../00_schema.sql). Do not use FINAL — ClickHouse Cloud's SharedMergeTree
-- rejects it outright on a non-Replacing table (ILLEGAL_FINAL).
CREATE TABLE IF NOT EXISTS inmobi.segment_anomalies (
  detected_at DateTime DEFAULT now(),
  dimension   LowCardinality(String),
  segment     LowCardinality(String),
  metric      LowCardinality(String),
  method      LowCardinality(String),
  time_window DateTime,
  observed    Nullable(Float64),
  expected    Nullable(Float64),
  delta       Nullable(Float64),
  pct_delta   Nullable(Float64),
  z           Float64,
  baseline_n  Nullable(UInt16)
) ENGINE = MergeTree ORDER BY (dimension, segment, metric, method, time_window);

ALTER TABLE inmobi.segment_anomalies MODIFY COLUMN observed Nullable(Float64);
ALTER TABLE inmobi.segment_anomalies MODIFY COLUMN expected Nullable(Float64);
ALTER TABLE inmobi.segment_anomalies MODIFY COLUMN delta Nullable(Float64);
ALTER TABLE inmobi.segment_anomalies MODIFY COLUMN baseline_n Nullable(UInt16);

-- All eligible segment scores, including non-anomalous rows. Unlike
-- segment_anomalies, this is not threshold-filtered: absence from the anomaly
-- table is not evidence that a segment was measured and ruled out. The
-- refreshable mv_segment_zr_hourly is the only writer and atomically replaces
-- this table on every refresh, so plain MergeTree is sufficient.
CREATE TABLE IF NOT EXISTS inmobi.segment_zr_hourly (
  computed_at DateTime DEFAULT now(),
  dimension   LowCardinality(String),
  segment     String,
  metric      LowCardinality(String),
  hour_ts     DateTime,
  observed    Float64,
  expected    Float64,
  pct_delta   Nullable(Float64),
  z           Float64,
  baseline_n  UInt16
) ENGINE = MergeTree ORDER BY (metric, dimension, segment, hour_ts);

-- Compact evidence matrix consumed by the incident heatmap. One row answers
-- "did this segment move with this incident?" with both incident-local and
-- prior-28-day evidence. It is derived by mv_segment_incident_evidence.
CREATE TABLE IF NOT EXISTS inmobi.segment_incident_evidence (
  refreshed_at             DateTime DEFAULT now(),
  metric                   LowCardinality(String),
  incident_start           DateTime,
  incident_end             DateTime,
  dimension                LowCardinality(String),
  segment                  String,
  peak_z                   Float64,
  mean_z                   Float64,
  global_peak_z            Float64,
  global_mean_z            Float64,
  incident_correlation     Nullable(Float64),
  incident_correlation_n   UInt16,
  baseline_correlation     Nullable(Float64),
  baseline_correlation_n   UInt16,
  direction_match_pct      Float64,
  scored_hours             UInt16,
  quiet_hours              UInt16
) ENGINE = MergeTree
ORDER BY (metric, incident_start, incident_end, dimension, segment);
