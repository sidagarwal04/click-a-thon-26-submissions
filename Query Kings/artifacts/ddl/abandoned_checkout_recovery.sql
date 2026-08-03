CREATE TABLE IF NOT EXISTS silver.abandoned_checkout_recovery_events
(
    event_name LowCardinality(String),
    event_id String,
    timestamp DateTime64(3),
    ingested_at DateTime DEFAULT now(),
    job_id String,
    app_version LowCardinality(String),
    application_id String,
    channel Nullable(String),
    city LowCardinality(String),
    client_lib LowCardinality(String),
    destination LowCardinality(String),
    device_type LowCardinality(String),
    drop_step LowCardinality(String),
    geoip_country_code LowCardinality(String),
    hours_since_drop Nullable(UInt8),
    os Nullable(String),
    user_id String,
    raw_json String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 18 MONTH;
