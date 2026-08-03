-- Schema:       unseen_data  (Promo / Coupon at Checkout)
-- Source NDJSON: Atlys/specs/unseen_data/events.ndjson  (5,364 rows, 2026-06-08 → 2026-06-28)
-- Database:      atlys
-- Base table:    atlys.promo_coupon_checkout   (one JSON column `payload`; every raw event wrapped as {"payload": <row>})
-- MVs:           atlys.coupon_funnel_daily_mv   -> atlys.coupon_funnel_daily_agg     (M1/M2/M3/M5: apply rate, valid/reject mix, conversion-lift cohort, segment cuts)
--                atlys.coupon_discount_daily_mv -> atlys.coupon_discount_daily_agg   (M4/M5: margin cost by coupon_code, segment cuts)
-- Design:        Discriminator payload.event (coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon).
--                ORDER BY = (event, application_id, device_type, geoip_country_code, timestamp) — 5 cols, discriminator -> frequent LowCard dims -> timestamp last.
--                user_id dropped from key (high-card, not a frequent filter) but typed for the cohort MV. coupon_code nullable -> NOT in key, bloom-indexed instead.
--                Typed-in-hint: only ORDER BY paths + skip-indexed string paths (os, coupon_code, reject_reason). Numeric discount_amount skip-indexed via CAST minmax (not typed).
--                Cloud target: plain MergeTree / AggregatingMergeTree only. ch_insert_time MATERIALIZED now64(3); PARTITION BY toYYYYMMDD(ch_insert_time); 90-day TTL (ttl_only_drop_parts=1).
--                MV backing tables carry agg_insert_time (compute-time watermark); their TTL keys on agg_insert_time, NOT the event-day column.
-- ClickHouse best-practices: schema-json-when-to-use (variable per-event-type paths -> single JSON payload); schema-pk-cardinality-order (low-card discriminator/dims leftmost, high-card user_id excluded); schema-partition-lifecycle (daily partition + drop-parts TTL).

CREATE DATABASE IF NOT EXISTS atlys;

-- ============================================================================
-- Base table
-- ============================================================================
CREATE TABLE IF NOT EXISTS atlys.promo_coupon_checkout
(
    payload JSON(
        event              LowCardinality(String),
        application_id     LowCardinality(String),
        device_type        LowCardinality(String),
        geoip_country_code LowCardinality(String),
        user_id            String,
        timestamp          DateTime64(3, 'UTC'),
        os                 LowCardinality(String),
        coupon_code        String,
        reject_reason      LowCardinality(String)
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    INDEX idx_os              payload.os            TYPE set(100)          GRANULARITY 4,
    INDEX idx_coupon_code     payload.coupon_code   TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_reject_reason   payload.reject_reason TYPE set(8)            GRANULARITY 4,
    INDEX idx_discount_amount CAST(payload.discount_amount AS Float64) TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.device_type, payload.geoip_country_code, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

-- ============================================================================
-- MV 1 — coupon funnel / counts / cohort (serves M1 apply rate, M2 valid-reject mix,
--        M3 conversion-lift cohort via uniqState(user_id), M5 segment cuts)
-- ============================================================================
CREATE TABLE IF NOT EXISTS atlys.coupon_funnel_daily_agg
(
    event_day          Date,
    event_type         LowCardinality(String),
    device_type        LowCardinality(String),
    geoip_country_code LowCardinality(String),
    coupon_code        String,
    reject_reason      LowCardinality(String),
    events_state       AggregateFunction(count),
    users_state        AggregateFunction(uniq, String),
    agg_insert_time    DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_day)
ORDER BY (event_type, device_type, geoip_country_code, coupon_code, reject_reason, event_day)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.coupon_funnel_daily_mv
TO atlys.coupon_funnel_daily_agg
AS
SELECT
    toDate(payload.timestamp)                                 AS event_day,
    CAST(payload.event AS String)                             AS event_type,
    COALESCE(CAST(payload.device_type AS String), '')        AS device_type,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    COALESCE(CAST(payload.coupon_code AS String), '')        AS coupon_code,
    COALESCE(CAST(payload.reject_reason AS String), '')      AS reject_reason,
    countState()                                             AS events_state,
    uniqState(CAST(payload.user_id AS String))               AS users_state
FROM atlys.promo_coupon_checkout
GROUP BY event_day, event_type, device_type, geoip_country_code, coupon_code, reject_reason;

-- ============================================================================
-- MV 2 — margin cost / discount economics (serves M4 margin cost by coupon_code, M5 segment cuts)
--        Filtered to events carrying discount_amount (applied / discount_shown / checkout).
-- ============================================================================
CREATE TABLE IF NOT EXISTS atlys.coupon_discount_daily_agg
(
    event_day             Date,
    coupon_code           String,
    device_type           LowCardinality(String),
    geoip_country_code    LowCardinality(String),
    destination           LowCardinality(String),
    discount_amount_state AggregateFunction(sum, Float64),
    cart_value_state      AggregateFunction(sum, Float64),
    final_value_state     AggregateFunction(sum, Float64),
    events_state          AggregateFunction(count),
    agg_insert_time       DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_day)
ORDER BY (coupon_code, device_type, geoip_country_code, destination, event_day)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.coupon_discount_daily_mv
TO atlys.coupon_discount_daily_agg
AS
SELECT
    toDate(payload.timestamp)                                 AS event_day,
    COALESCE(CAST(payload.coupon_code AS String), '')        AS coupon_code,
    COALESCE(CAST(payload.device_type AS String), '')        AS device_type,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    COALESCE(CAST(payload.destination AS String), '')        AS destination,
    sumState(CAST(payload.discount_amount AS Float64))        AS discount_amount_state,
    sumState(CAST(payload.cart_value AS Float64))             AS cart_value_state,
    sumState(CAST(payload.final_value AS Float64))            AS final_value_state,
    countState()                                              AS events_state
FROM atlys.promo_coupon_checkout
WHERE payload.discount_amount IS NOT NULL
GROUP BY event_day, coupon_code, device_type, geoip_country_code, destination;
