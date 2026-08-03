-- Long-format hourly rollup: one row per (hour, dimension, value).
-- The single surface for detection sweeps, HyperDX charts/alerts, and Q2 first passes.
--
-- Design rules:
--  * ADDITIVE COUNTERS ONLY — every ratio is derived sum/sum at read time, so any
--    regrouping (hour -> incident window -> day) stays glossary-exact and alert
--    numbers always reconcile with investigator numbers.
--  * ORDER BY (dimension, value, window_start) stores each series contiguously:
--    an alert poll or baseline window reads a few granules, not the table.
--  * SummingMergeTree merges are eventual — ALWAYS aggregate on read:
--    SELECT sum(requests) ... GROUP BY, never trust a raw row.
--  * dataset is deliberately NOT in the key: the unseen slice must share baselines
--    with dev history (it continues the same universe).
--
-- Series emitted per event (13): global, region, country, device_model, os_version,
-- ad_format, category, publisher_tier, vertical, campaign_type, app_id, advertiser_id.
-- Empty advertiser-side values ('' = unfilled) are labeled '(none)' so charts and
-- GROUP BYs never show a blank series.

CREATE TABLE IF NOT EXISTS rca.metrics_hourly_by_dim
(
    window_start DateTime('UTC'),
    dimension    LowCardinality(String),
    value        LowCardinality(String),
    requests     UInt64,
    fills        UInt64,
    impressions  UInt64,
    clicks       UInt64,
    revenue      Float64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(window_start)
ORDER BY (dimension, value, window_start);

CREATE MATERIALIZED VIEW IF NOT EXISTS rca.mv_metrics_by_dim TO rca.metrics_hourly_by_dim AS
SELECT
    toStartOfHour(event_time) AS window_start,
    dim.1 AS dimension,
    dim.2 AS value,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM rca.ad_events_enriched
ARRAY JOIN
    [
        ('global',         'all'),
        ('region',         region),
        ('country',        country),
        ('device_model',   device_model),
        ('os_version',     os_version),
        ('ad_format',      ad_format),
        ('category',       category),
        ('publisher_tier', publisher_tier),
        ('vertical',       if(vertical = '',      '(none)', vertical)),
        ('campaign_type',  if(campaign_type = '', '(none)', campaign_type)),
        ('app_id',         app_id),
        ('advertiser_id',  if(advertiser_id = '', '(none)', advertiser_id))
    ] AS dim
GROUP BY window_start, dimension, value;
