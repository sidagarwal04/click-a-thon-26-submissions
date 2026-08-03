-- FeatureLens generated ClickHouse schemas for the five known Atlys features.
-- Captured from the final retained-table replay on 2026-08-02.

-- Express Checkout · run_600a65ebcf281c14
CREATE TABLE featurelens_poc.express_checkout_events_v1
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
    `city` String,
    `client_lib` String,
    `currency` LowCardinality(Nullable(String)),
    `eligible` Nullable(UInt8),
    `otp_attempts` Nullable(Int64),
    `otp_success` Nullable(UInt8),
    `payment_amount` Nullable(Int64),
    `payment_currency` LowCardinality(Nullable(String)),
    `payment_latency_ms` Nullable(Int64),
    `saved_method_type` Nullable(String),
    `shown_amount` Nullable(Int64)
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

-- Group / Family · run_f47513a713dde385
CREATE TABLE featurelens_poc.group_family_events_v2
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
    `city` String,
    `client_lib` String,
    `docs_complete` Nullable(UInt8),
    `group_id` String,
    `group_size` Int64,
    `relation` LowCardinality(Nullable(String)),
    `traveller_index` Nullable(Int64),
    `travellers_submitted` Nullable(Int64)
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

-- Status Sharing · run_f9f799a75821339d
CREATE TABLE featurelens_poc.status_sharing_events_v2
(
    `event_name` LowCardinality(String),
    `id` String,
    `timestamp` DateTime64(3, 'UTC'),
    `user_id` Nullable(String),
    `application_id` Nullable(String),
    `destination` LowCardinality(String),
    `device_type` LowCardinality(Nullable(String)),
    `os` LowCardinality(Nullable(String)),
    `app_version` LowCardinality(Nullable(String)),
    `geoip_country_code` LowCardinality(Nullable(String)),
    `channel` LowCardinality(Nullable(String)),
    `city` Nullable(String),
    `client_lib` Nullable(String),
    `cta` Nullable(String),
    `recipient_is_new_user` Nullable(UInt8),
    `share_id` String,
    `status_shared` Nullable(String)
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

-- Abandoned Checkout Recovery · run_b1ca62003bb19734
CREATE TABLE featurelens_poc.abandoned_checkout_recovery_events_v2
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
    `channel` LowCardinality(Nullable(String)),
    `city` String,
    `client_lib` String,
    `drop_step` LowCardinality(String),
    `hours_since_drop` Nullable(Int64)
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

-- Instant Forex · run_b833d7e0bd3e9e83
CREATE TABLE featurelens_poc.instant_forex_events_v2
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
    `addon_value_inr` Nullable(Int64),
    `amount` Nullable(Int64),
    `city` String,
    `client_lib` String,
    `from_currency` LowCardinality(String),
    `fx_rate` Nullable(Float64),
    `to_currency` LowCardinality(String)
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
