CREATE DATABASE IF NOT EXISTS `inmobi-hari`;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.apps (
    app_id String, category LowCardinality(String), publisher_tier LowCardinality(String)
) ENGINE = MergeTree ORDER BY app_id;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.geo_device (
    geo_device_id String, region LowCardinality(String), country LowCardinality(String),
    device_model LowCardinality(String), os_version LowCardinality(String)
) ENGINE = MergeTree ORDER BY geo_device_id;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.advertisers (
    advertiser_id String, vertical LowCardinality(String), campaign_type LowCardinality(String)
) ENGINE = MergeTree ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.ad_events (
    event_time    DateTime64(3,'UTC'),
    app_id        String,
    geo_device_id String,
    advertiser_id String,
    ad_format     LowCardinality(String),
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64
) ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (toStartOfHour(event_time), app_id);
