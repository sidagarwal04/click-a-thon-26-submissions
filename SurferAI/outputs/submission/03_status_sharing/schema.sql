CREATE TABLE IF NOT EXISTS status_sharing_events (
    event LowCardinality(String),
    id String,
    timestamp DateTime,
    device_type LowCardinality(String),
    os LowCardinality(String),
    app_version LowCardinality(String),
    geoip_country_code LowCardinality(String),
    city LowCardinality(String),
    client_lib LowCardinality(String),
    user_id Nullable(String),
    application_id Nullable(String),
    share_id String,
    destination String,
    status_shared LowCardinality(String),
    channel LowCardinality(String),
    recipient_is_new_user UInt8,
    cta LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (timestamp, user_id)
ORDER BY (timestamp, user_id)
TTL timestamp + INTERVAL 12 MONTH
SETTINGS index_granularity = 8192;

-- justification: daily segment rollup for accelerated dashboard query execution
CREATE MATERIALIZED VIEW IF NOT EXISTS status_sharing_events_daily_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (device_type, os, geoip_country_code, destination, channel, date, event)
AS SELECT
    toYYYYMMDD(timestamp) AS date,
    device_type, os, geoip_country_code, destination, channel, event,
    count() AS total_events,
    uniqState(user_id) AS unique_users
FROM status_sharing_events
GROUP BY device_type, os, geoip_country_code, destination, channel, date, event;
