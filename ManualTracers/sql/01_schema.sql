-- =====================================================================
-- 01 · BRONZE — landing tables (raw, exactly as delivered)
-- InMobi Click-a-thon 2026 · automated root-cause analyst
-- =====================================================================
-- ad_events is the ONLY table replayed for the sealed dataset.
-- Dimension tables are reference data and change rarely.

CREATE DATABASE IF NOT EXISTS inmobi;

-- ---------------------------------------------------------------------
-- Fact: one row per ad request.
-- ORDER BY leads with event_time because every detection and drill-down
-- query is time-bounded first, then filtered by dimension.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.ad_events
(
    event_time    DateTime64(3),
    app_id        LowCardinality(String),
    geo_device_id LowCardinality(String),
    advertiser_id LowCardinality(String),  -- '' when the request was not filled
    ad_format     LowCardinality(String),
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, app_id, geo_device_id, ad_format)
SETTINGS index_granularity = 8192;

-- ---------------------------------------------------------------------
-- Dimensions. Small, static, and backed by dictionaries (see 02).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.apps
(
    app_id         String,
    category       String,
    publisher_tier String
)
ENGINE = MergeTree ORDER BY app_id;

CREATE TABLE IF NOT EXISTS inmobi.advertisers
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
ENGINE = MergeTree ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS inmobi.geo_device
(
    geo_device_id String,
    region        String,   -- NAM / EU / APAC / LATAM / MEA  (NAM, never NA)
    country       String,
    device_model  String,
    os_version    String
)
ENGINE = MergeTree ORDER BY geo_device_id;
