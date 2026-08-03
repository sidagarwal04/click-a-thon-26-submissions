-- InsightIQ ClickHouse view layer (live schema snapshot)
-- Database: insightiq
-- UI / API / engine query the pre-computed layer — never scan ad_events_raw for product paths.

-- =============================================================================
-- Pipeline
-- =============================================================================
-- ad_events_raw  (9M facts)
--      │
--      ▼  MATERIALIZED VIEW mv_hourly
-- agg_hourly  (SharedSummingMergeTree, ~8.9M)
--      │
--      ▼  VIEW metric_hourly_snapshot  (adds fill_rate, ctr, ecpm, rpr)
-- metric_hourly_snapshot
--      │
--      ├─► baseline_hourly  (SharedReplacingMergeTree)
--      │         │
--      │         ▼
--      └─► alerts_live  (~93k, |z| > 3)
--                │
--                ├─► alert_dimension_contributors  (~714k)
--                └─► alert_observations            (~714k)
--
-- alert_rules  (policy table, currently 4 rows)

-- =============================================================================
-- Objects (as deployed)
-- =============================================================================

-- Raw fact (ingest only)
-- CREATE TABLE insightiq.ad_events_raw (...);

-- Hourly rollup target for mv_hourly
-- CREATE TABLE insightiq.agg_hourly (
--   bucket DateTime,
--   ad_format, app_id, category, publisher_tier, advertiser_id, vertical,
--   campaign_type, geo_device_id, region, country, device_model, os_version,
--   requests, fills, impressions, clicks, revenue
-- ) ENGINE = SharedSummingMergeTree ...

-- CREATE MATERIALIZED VIEW insightiq.mv_hourly TO insightiq.agg_hourly AS
-- SELECT toStartOfHour(ts) AS bucket, ... FROM ad_events_raw ...;

-- Derived metrics VIEW used by dashboard + RCA math (re-aggregates SummingMergeTree parts):
-- CREATE VIEW insightiq.metric_hourly_snapshot AS
-- SELECT ..., requests_sum AS requests, ...,
--        fills_sum / nullIf(requests_sum,0) AS fill_rate,
--        clicks_sum / nullIf(impressions_sum,0) AS ctr,
--        (revenue_sum / nullIf(impressions_sum,0)) * 1000 AS ecpm,
--        revenue_sum / nullIf(requests_sum,0) AS rpr
-- FROM (
--   SELECT bucket, dimensions..., sum(requests) AS requests_sum, ...
--   FROM insightiq.agg_hourly
--   GROUP BY bucket, dimensions...
-- );

-- CREATE TABLE insightiq.baseline_hourly (
--   advertiser_id, metric, bucket, expected, stddev, median, mad,
--   lower_bound, upper_bound, created_at
-- ) ENGINE = SharedReplacingMergeTree(..., created_at)
-- ORDER BY (advertiser_id, metric, bucket);

-- CREATE TABLE insightiq.alerts_live (
--   alert_id UUID,
--   advertiser_id String,
--   metric String,              -- revenue | ecpm | ctr | ...
--   granularity String,
--   bucket DateTime,
--   actual Float64,
--   expected Float64,
--   zscore Float64,
--   created_at DateTime DEFAULT now()
-- ) ENGINE = SharedMergeTree
-- ORDER BY (advertiser_id, metric, bucket);

-- CREATE TABLE insightiq.alert_dimension_contributors (
--   alert_id UUID,
--   dimension String,
--   dimension_value String,
--   current_value Float64,
--   baseline_value Float64,
--   delta Float64,
--   contribution Float64
-- ) ENGINE = SharedMergeTree
-- ORDER BY (alert_id, dimension);

-- CREATE TABLE insightiq.alert_observations (
--   alert_id UUID,
--   observation_order UInt32,
--   observation_type String,
--   title String,
--   detail String,
--   impact Float64
-- ) ENGINE = SharedMergeTree
-- ORDER BY (alert_id, observation_order);

-- Live alert_rules schema (differs from older drafts that used advertiser_id/sensitivity/enabled):
-- CREATE TABLE insightiq.alert_rules (
--   rule_id UUID,
--   name String,
--   metric String,
--   granularity String,
--   threshold Float64,
--   min_volume Float64,
--   consecutive_buckets UInt32,
--   dimensions Array(String),
--   created_at DateTime DEFAULT now()
-- ) ENGINE = SharedMergeTree
-- ORDER BY rule_id;

-- =============================================================================
-- Product queries (engine / UI)
-- =============================================================================

-- Alert wall
-- SELECT
--     toString(a.alert_id) AS id,
--     a.advertiser_id,
--     a.metric,
--     toString(a.bucket) AS bucket,
--     a.actual, a.expected, a.zscore
-- FROM insightiq.alerts_live AS a
-- WHERE abs(a.zscore) > 3
-- ORDER BY abs(a.zscore) DESC
-- LIMIT 28;

-- Peak anomaly per advertiser
-- SELECT ... FROM (
--   SELECT *, row_number() OVER (
--     PARTITION BY advertiser_id ORDER BY abs(zscore) DESC
--   ) AS rn
--   FROM insightiq.alerts_live
--   WHERE abs(zscore) > 3
-- ) WHERE rn = 1
-- ORDER BY abs(zscore) DESC
-- LIMIT 28;

-- Contributors / observations for one alert
-- SELECT dimension, dimension_value, current_value, baseline_value, delta, contribution
-- FROM insightiq.alert_dimension_contributors
-- WHERE alert_id = toUUID({alert_id})
-- ORDER BY abs(delta) DESC;

-- SELECT observation_order, observation_type, title, detail, impact
-- FROM insightiq.alert_observations
-- WHERE alert_id = toUUID({alert_id})
-- ORDER BY observation_order;

-- Dashboard date bounds (prefer physical table)
-- SELECT min(bucket), max(bucket) FROM insightiq.agg_hourly;

-- List rules
-- SELECT toString(rule_id) AS rule_id, name, metric, granularity,
--        threshold, min_volume, consecutive_buckets, dimensions, created_at
-- FROM insightiq.alert_rules
-- ORDER BY created_at DESC;
