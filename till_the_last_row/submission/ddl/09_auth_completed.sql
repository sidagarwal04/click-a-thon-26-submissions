-- ============================================================================
-- Atlys schema: 09_auth_completed
-- Spec        : specs/09_auth_completed/spec.md
-- Event(s)    : auth_completed  (single event type -> one base table)
-- Database    : atlys
-- Target      : ClickHouse Cloud (plain MergeTree; Cloud auto-maps to Shared*)
-- ----------------------------------------------------------------------------
-- Design notes:
--   * One base table, single JSON column `payload`. Only ORDER BY / PARTITION BY
--     paths + string/bool skip-index paths are typed; numeric paths stay untyped
--     and are indexed via CAST(...) minmax.
--   * ORDER BY (<=5 cols): event, application_id, auth_method, user_id, timestamp.
--     `os` is null on some rows -> excluded from key; typed + skip-indexed instead.
--   * ch_insert_time drives PARTITION BY + 90d TTL (ttl_only_drop_parts=1).
--   * One AggregatingMergeTree MV serves PM metrics M1/M2/M3/M5.
--     M4 is cross-event and is not served by an MV (see metrics manifest).
--   * acquisition_channel is DERIVED (user-confirmed): gclid!=''->paid_google,
--     fbclid!=''->paid_meta, else organic.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS atlys;

-- ---------------------------------------------------------------------------
-- Base table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atlys.auth_completed
(
    payload JSON(
        event LowCardinality(String),
        application_id LowCardinality(String),
        auth_method LowCardinality(String),
        user_id String,
        timestamp DateTime64(3, 'UTC'),
        device_type LowCardinality(String),
        os LowCardinality(String),
        geoip_country_code LowCardinality(String),
        is_new_user Bool
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),

    INDEX idx_device_type payload.device_type TYPE set(0) GRANULARITY 1,
    INDEX idx_os payload.os TYPE set(0) GRANULARITY 1,
    INDEX idx_country payload.geoip_country_code TYPE set(0) GRANULARITY 1,
    INDEX idx_is_new_user payload.is_new_user TYPE set(2) GRANULARITY 1,
    INDEX idx_attempts CAST(payload.attempts AS UInt32) TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.auth_method, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY
SETTINGS ttl_only_drop_parts = 1;

-- ---------------------------------------------------------------------------
-- Metrics aggregate (backing table for the MV) — serves M1/M2/M3/M5
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atlys.auth_completed_metrics_agg
(
    day Date,
    auth_method LowCardinality(String),
    device_type LowCardinality(String),
    os LowCardinality(String),
    geoip_country_code LowCardinality(String),
    acquisition_channel LowCardinality(String),
    is_new_user UInt8,
    completions AggregateFunction(count),
    new_user_completions AggregateFunction(sum, UInt64),
    retried_completions AggregateFunction(sum, UInt64),
    total_attempts AggregateFunction(sum, UInt64),
    agg_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, auth_method, device_type, os, geoip_country_code, acquisition_channel, is_new_user)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY
SETTINGS ttl_only_drop_parts = 1;

-- ---------------------------------------------------------------------------
-- Materialized view: base -> metrics aggregate
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.auth_completed_metrics_mv
TO atlys.auth_completed_metrics_agg
AS
SELECT
    toDate(payload.timestamp) AS day,
    COALESCE(CAST(payload.auth_method AS String), '') AS auth_method,
    COALESCE(CAST(payload.device_type AS String), '') AS device_type,
    COALESCE(CAST(payload.os AS String), '') AS os,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    multiIf(
        CAST(payload.gclid AS String) != '', 'paid_google',
        CAST(payload.fbclid AS String) != '', 'paid_meta',
        'organic'
    ) AS acquisition_channel,
    toUInt8(payload.is_new_user) AS is_new_user,
    countState() AS completions,
    sumState(toUInt64(payload.is_new_user = 1)) AS new_user_completions,
    sumState(toUInt64(CAST(payload.attempts AS UInt32) > 1)) AS retried_completions,
    sumState(toUInt64(CAST(payload.attempts AS UInt32))) AS total_attempts
FROM atlys.auth_completed
WHERE payload.event = 'auth_completed'
GROUP BY
    day,
    auth_method,
    device_type,
    os,
    geoip_country_code,
    acquisition_channel,
    is_new_user;
