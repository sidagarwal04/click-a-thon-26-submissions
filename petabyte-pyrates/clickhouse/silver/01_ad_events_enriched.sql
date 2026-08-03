CREATE TABLE silver.ad_events_enriched
(
    `event_time` DateTime('UTC'),
    `event_date` Date MATERIALIZED toDate(event_time),
    `ad_format` LowCardinality(String),
    `app_id` String,
    `geo_device_id` String,
    `advertiser_id` String,
    `is_filled` UInt8,
    `is_impression` UInt8,
    `is_click` UInt8,
    `revenue` Float32
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_date, ad_format, app_id, geo_device_id, event_time)
SETTINGS index_granularity = 8192
COMMENT 'Typed, funnel-shaped ad events. Append-only mirror of default.clickathon_ad_events.'
