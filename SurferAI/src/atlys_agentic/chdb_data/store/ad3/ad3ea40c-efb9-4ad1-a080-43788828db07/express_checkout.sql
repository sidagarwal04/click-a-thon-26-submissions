ATTACH TABLE _ UUID '43af2e81-b6c3-4c3e-aaef-f02f914ee1af'
(
    `event` LowCardinality(String),
    `id` String,
    `timestamp` DateTime,
    `device_type` LowCardinality(String),
    `os` LowCardinality(String),
    `app_version` LowCardinality(String),
    `geoip_country_code` LowCardinality(String),
    `city` LowCardinality(String),
    `client_lib` LowCardinality(String),
    `user_id` String,
    `application_id` String,
    `destination` String,
    `eligible` UInt8,
    `shown_amount` Nullable(Float64),
    `currency` LowCardinality(String),
    `saved_method_type` LowCardinality(String),
    `otp_attempts` Nullable(Int64),
    `otp_success` UInt8,
    `payment_amount` Nullable(Float64),
    `payment_currency` LowCardinality(String),
    `payment_latency_ms` Nullable(Int64)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (timestamp, user_id)
ORDER BY (timestamp, user_id)
TTL timestamp + toIntervalMonth(12)
SETTINGS index_granularity = 8192
