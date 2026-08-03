CREATE TABLE IF NOT EXISTS silver.group_family_events
(
    job_id String,
    event_name LowCardinality(String),
    event_id String,
    timestamp DateTime64(3),
    app_version LowCardinality(String),
    application_id String,
    city LowCardinality(String),
    client_lib LowCardinality(String),
    destination LowCardinality(String),
    device_type LowCardinality(String),
    docs_complete Nullable(Bool),
    geoip_country_code LowCardinality(String),
    group_id String,
    group_size UInt8,
    os Nullable(String),
    relation Nullable(String),
    traveller_index Nullable(UInt8),
    travellers_submitted Nullable(UInt8),
    user_id String,
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 18 MONTH;
