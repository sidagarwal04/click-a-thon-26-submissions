CREATE TABLE IF NOT EXISTS silver.instant_forex_events
(
    event_name LowCardinality(String),
    event_id String,
    timestamp DateTime64(3),
    job_id String,
    addon_value_inr Nullable(Float64),
    amount Nullable(Float64),
    app_version LowCardinality(String),
    application_id String,
    city LowCardinality(String),
    client_lib LowCardinality(String),
    destination LowCardinality(String),
    device_type LowCardinality(String),
    from_currency LowCardinality(String),
    fx_rate Nullable(Float64),
    geoip_country_code LowCardinality(String),
    os Nullable(String),
    to_currency LowCardinality(String),
    user_id String,
    raw_json String,
    ingested_at DateTime DEFAULT now(),
    device LowCardinality(String),
    geoip_country LowCardinality(String)
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 18 MONTH;
