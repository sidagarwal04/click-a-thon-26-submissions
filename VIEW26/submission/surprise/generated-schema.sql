CREATE TABLE featurelens_poc.promo_coupon_at_checkout_events_v6
(
    `event_name` LowCardinality(String),
    `id` String,
    `timestamp` DateTime64(3, 'UTC'),
    `user_id` String,
    `application_id` String,
    `destination` LowCardinality(String),
    `device_type` LowCardinality(String),
    `os` LowCardinality(Nullable(String)),
    `app_version` LowCardinality(String),
    `geoip_country_code` LowCardinality(String),
    `cart_value` Int64,
    `city` String,
    `client_lib` String,
    `coupon_code` Nullable(String),
    `currency` LowCardinality(String),
    `discount_amount` Nullable(Int64),
    `discount_type` Nullable(String),
    `final_value` Nullable(Int64),
    `reject_reason` Nullable(String)
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY
(
    toDate(timestamp),
    event_name,
    ifNull(destination, ''),
    ifNull(device_type, ''),
    ifNull(application_id, ''),
    ifNull(user_id, ''),
    timestamp
)
SETTINGS index_granularity = 8192;
