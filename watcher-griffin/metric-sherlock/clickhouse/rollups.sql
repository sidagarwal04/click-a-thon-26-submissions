-- Hourly pre-aggregated rollups, one per candidate slicing dimension, so the
-- investigation engine never has to scan all 9M raw rows to find which
-- segment moved. Run after schema.sql and dictionaries.sql, before load.sql
-- (materialized views only fire on rows inserted after creation, so creating
-- these first lets the bulk load into ad_events backfill them for free).
--
-- Design note: a single table grouped by (hour, app, geo, advertiser) was
-- considered and rejected — with 2,000 apps x 5,000 geo_devices x 500
-- advertisers, that cross-product has as many distinct combinations as there
-- are raw rows, so it wouldn't actually shrink the scan. Instead there's one
-- narrow table per dimension: cardinality stays low (5-2,000 distinct values)
-- so each is a small fraction of the raw table's size, and every drill-down
-- query becomes the same simple shape: "GROUP BY value, compare window vs
-- baseline" reused across whichever dimension is being checked.
--
-- All metrics are plain sums (see Docs/metrics_glossary.md), so
-- SummingMergeTree is sufficient -- no AggregatingMergeTree/-State needed.
-- Always wrap columns in sum(...) when querying, since SummingMergeTree only
-- merges same-key rows in the background.

-- === Top-level series, for the anomaly-detection step itself ===
CREATE TABLE hourly_overall
(
    hour        DateTime,
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Decimal64(6)
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY hour;

CREATE MATERIALIZED VIEW mv_hourly_overall TO hourly_overall AS
SELECT
    toStartOfHour(event_time) AS hour,
    count()             AS requests,
    sum(is_filled)      AS fills,
    sum(is_impression)  AS impressions,
    sum(is_click)       AS clicks,
    sum(revenue)        AS revenue
FROM ad_events
GROUP BY hour;

-- === Direct event-level dimensions (no dictionary lookup needed) ===

CREATE TABLE hourly_by_app
(
    hour DateTime, app_id LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, app_id);

CREATE MATERIALIZED VIEW mv_hourly_by_app TO hourly_by_app AS
SELECT toStartOfHour(event_time) AS hour, app_id,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, app_id;

CREATE TABLE hourly_by_advertiser
(
    hour DateTime, advertiser_id LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, advertiser_id);

CREATE MATERIALIZED VIEW mv_hourly_by_advertiser TO hourly_by_advertiser AS
SELECT toStartOfHour(event_time) AS hour, advertiser_id,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, advertiser_id;

CREATE TABLE hourly_by_format
(
    hour DateTime, ad_format LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, ad_format);

CREATE MATERIALIZED VIEW mv_hourly_by_format TO hourly_by_format AS
SELECT toStartOfHour(event_time) AS hour, ad_format,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, ad_format;

-- === geo_device-derived dimensions (via geo_device_dict) ===

CREATE TABLE hourly_by_region
(
    hour DateTime, region LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, region);

CREATE MATERIALIZED VIEW mv_hourly_by_region TO hourly_by_region AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('geo_device_dict', 'region', geo_device_id) AS region,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, region;

CREATE TABLE hourly_by_country
(
    hour DateTime, country LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, country);

CREATE MATERIALIZED VIEW mv_hourly_by_country TO hourly_by_country AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('geo_device_dict', 'country', geo_device_id) AS country,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, country;

CREATE TABLE hourly_by_device_model
(
    hour DateTime, device_model LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, device_model);

CREATE MATERIALIZED VIEW mv_hourly_by_device_model TO hourly_by_device_model AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('geo_device_dict', 'device_model', geo_device_id) AS device_model,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, device_model;

CREATE TABLE hourly_by_os_version
(
    hour DateTime, os_version LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, os_version);

CREATE MATERIALIZED VIEW mv_hourly_by_os_version TO hourly_by_os_version AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('geo_device_dict', 'os_version', geo_device_id) AS os_version,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, os_version;

-- === apps-derived dimensions (via apps_dict) ===

CREATE TABLE hourly_by_category
(
    hour DateTime, category LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, category);

CREATE MATERIALIZED VIEW mv_hourly_by_category TO hourly_by_category AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('apps_dict', 'category', app_id) AS category,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, category;

CREATE TABLE hourly_by_publisher_tier
(
    hour DateTime, publisher_tier LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, publisher_tier);

CREATE MATERIALIZED VIEW mv_hourly_by_publisher_tier TO hourly_by_publisher_tier AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('apps_dict', 'publisher_tier', app_id) AS publisher_tier,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, publisher_tier;

-- === advertisers-derived dimensions (via advertisers_dict) ===
-- advertiser_id is '' on unfilled requests, which has no dictionary entry --
-- use dictGetOrDefault so those rows fall into a '' bucket instead of erroring.

CREATE TABLE hourly_by_vertical
(
    hour DateTime, vertical LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, vertical);

CREATE MATERIALIZED VIEW mv_hourly_by_vertical TO hourly_by_vertical AS
SELECT toStartOfHour(event_time) AS hour,
       dictGetOrDefault('advertisers_dict', 'vertical', advertiser_id, '') AS vertical,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, vertical;

CREATE TABLE hourly_by_campaign_type
(
    hour DateTime, campaign_type LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, campaign_type);

CREATE MATERIALIZED VIEW mv_hourly_by_campaign_type TO hourly_by_campaign_type AS
SELECT toStartOfHour(event_time) AS hour,
       dictGetOrDefault('advertisers_dict', 'campaign_type', advertiser_id, '') AS campaign_type,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, campaign_type;
