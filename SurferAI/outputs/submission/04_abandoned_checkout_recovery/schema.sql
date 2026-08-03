CREATE TABLE IF NOT EXISTS abandoned_checkout_recovery (
    event LowCardinality(String),
    id String,
    timestamp DateTime,
    device_type LowCardinality(String),
    os LowCardinality(String),
    app_version LowCardinality(String),
    geoip_country_code LowCardinality(String),
    city LowCardinality(String),
    client_lib LowCardinality(String),
    user_id String,
    application_id String,
    destination String,
    drop_step LowCardinality(String),
    channel LowCardinality(String),
    hours_since_drop Nullable(Int64)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (timestamp, user_id)
ORDER BY (timestamp, user_id)
TTL timestamp + INTERVAL 12 MONTH
SETTINGS index_granularity = 8192;

-- justification: daily segment rollup for accelerated dashboard query execution
CREATE MATERIALIZED VIEW IF NOT EXISTS abandoned_checkout_recovery_daily_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (device_type, os, geoip_country_code, destination, channel, date, event)
AS SELECT
    toYYYYMMDD(timestamp) AS date,
    device_type, os, geoip_country_code, destination, channel, event,
    count() AS total_events,
    uniqState(user_id) AS unique_users
FROM abandoned_checkout_recovery
GROUP BY device_type, os, geoip_country_code, destination, channel, date, event;
