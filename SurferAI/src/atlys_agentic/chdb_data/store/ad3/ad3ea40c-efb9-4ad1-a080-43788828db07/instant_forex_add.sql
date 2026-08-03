ATTACH TABLE _ UUID 'ab86828e-3889-4eca-945b-9fc9473d9ad2'
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
    `from_currency` LowCardinality(String),
    `to_currency` LowCardinality(String),
    `fx_rate` Nullable(Float64),
    `amount` Nullable(Int64),
    `addon_value_inr` Nullable(Float64)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (timestamp, user_id)
ORDER BY (timestamp, user_id)
TTL timestamp + toIntervalMonth(12)
SETTINGS index_granularity = 8192
