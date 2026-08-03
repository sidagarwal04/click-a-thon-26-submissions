CREATE TABLE IF NOT EXISTS silver.status_sharing_events
(
    event_name LowCardinality(String),
    event_id String,
    timestamp DateTime64(3),
    job_id String,
    app_version Nullable(String),
    application_id Nullable(String),
    channel Nullable(String),
    city Nullable(String),
    client_lib Nullable(String),
    cta Nullable(String),
    destination LowCardinality(String),
    device_type Nullable(String),
    geoip_country_code Nullable(String),
    os Nullable(String),
    recipient_is_new_user Nullable(Bool),
    share_id String,
    status_shared Nullable(String),
    user_id Nullable(String),
    ingested_at DateTime DEFAULT now(),
    raw_json String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 18 MONTH;
