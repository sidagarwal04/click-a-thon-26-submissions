CREATE TABLE IF NOT EXISTS silver.promo_coupon_checkout_events
(
    job_id String,
    event_name LowCardinality(String),
    event_id String,
    timestamp DateTime64(3),
    app_version LowCardinality(String),
    application_id String,
    cart_value Float64,
    city LowCardinality(String),
    client_lib LowCardinality(String),
    coupon_code Nullable(String),
    currency LowCardinality(String),
    destination LowCardinality(String),
    device_type LowCardinality(String),
    device LowCardinality(String),
    geoip_country_code LowCardinality(String),
    geoip LowCardinality(String),
    addon_value_inr String,
    from_currency LowCardinality(String),
    fx_rate String,
    to_currency LowCardinality(String),
    os Nullable(String),
    reject_reason Nullable(String),
    user_id String,
    ingested_at DateTime DEFAULT now(),
    discount_amount Nullable(Float64),
    discount_type Nullable(String),
    final_value Nullable(Float64),
    raw_json String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 18 MONTH;
