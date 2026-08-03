CREATE TABLE IF NOT EXISTS express_checkout (
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
    eligible UInt8,
    shown_amount Nullable(Float64),
    currency LowCardinality(String),
    saved_method_type LowCardinality(String),
    otp_attempts Nullable(Int64),
    otp_success UInt8,
    payment_amount Nullable(Float64),
    payment_currency LowCardinality(String),
    payment_latency_ms Nullable(Int64)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (timestamp, user_id)
ORDER BY (timestamp, user_id)
TTL timestamp + INTERVAL 12 MONTH
SETTINGS index_granularity = 8192;

-- justification: daily segment rollup for accelerated dashboard query execution
CREATE MATERIALIZED VIEW IF NOT EXISTS express_checkout_daily_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (device_type, os, geoip_country_code, destination, date, event)
AS SELECT
    toYYYYMMDD(timestamp) AS date,
    device_type, os, geoip_country_code, destination, event,
    count() AS total_events,
    uniqState(user_id) AS unique_users
FROM express_checkout
GROUP BY device_type, os, geoip_country_code, destination, date, event;
