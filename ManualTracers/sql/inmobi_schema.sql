-- InMobi ad-events star schema for local ClickHouse (4c/8g-friendly MergeTree).
CREATE DATABASE IF NOT EXISTS inmobi;

CREATE TABLE IF NOT EXISTS inmobi.ad_events
(
    event_time    DateTime64(3),
    app_id        LowCardinality(String),
    geo_device_id LowCardinality(String),
    advertiser_id LowCardinality(String),  -- '' when unfilled
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

CREATE TABLE IF NOT EXISTS inmobi.apps
(
    app_id         LowCardinality(String),
    category       LowCardinality(String),
    publisher_tier LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY app_id;

CREATE TABLE IF NOT EXISTS inmobi.advertisers
(
    advertiser_id LowCardinality(String),
    vertical      LowCardinality(String),
    campaign_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS inmobi.geo_device
(
    geo_device_id LowCardinality(String),
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY geo_device_id;

-- Denormalized wide table for HyperDX single-source charts / drill-downs.
CREATE TABLE IF NOT EXISTS inmobi.ad_events_enriched
(
    event_time      DateTime64(3),
    app_id          LowCardinality(String),
    geo_device_id   LowCardinality(String),
    advertiser_id   LowCardinality(String),
    ad_format       LowCardinality(String),
    is_filled       UInt8,
    is_impression   UInt8,
    is_click        UInt8,
    revenue         Float64,
    category        LowCardinality(String),
    publisher_tier  LowCardinality(String),
    region          LowCardinality(String),
    country         LowCardinality(String),
    device_model    LowCardinality(String),
    os_version      LowCardinality(String),
    vertical        LowCardinality(String),
    campaign_type   LowCardinality(String),
    -- HyperDX-friendly log-style body for Search UI
    message         String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, region, country, os_version, category, ad_format)
SETTINGS index_granularity = 8192;
