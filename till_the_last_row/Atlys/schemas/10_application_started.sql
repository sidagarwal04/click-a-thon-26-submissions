-- Schema: 10_application_started
-- Source NDJSON: /app/specs/10_application_started/events.ndjson
-- Database: atlys
-- Base table: application_started  (ONE table per spec — all event types land here)
-- MVs: mv_application_started_daily (-> application_started_daily)
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)

CREATE DATABASE IF NOT EXISTS atlys;

-- ─────────────────────────────────────────────────────────────────────────────
-- Base table: one JSON `payload` column absorbs the full event envelope.
-- Typed hints ONLY for: ORDER BY paths, skip-indexed hot filters, and the bool.
-- ORDER BY: discriminator -> destination -> purpose -> user_id -> timestamp (<=5).
--   destination + purpose appear in the most PM questions (Q1, Q5), so they lead.
-- Hot filters not in the key (flow, eta_shown, citizenship, device_type, os,
--   is_back_filled) get data-skipping indexes.
-- os / duplicate_id are Nullable in the source -> os kept OUT of the key (skip-
--   indexed instead); duplicate_id stays untyped in payload.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlys.application_started
(
    payload JSON(
        event            LowCardinality(String),   -- event-type discriminator; leftmost of key
        application_id   LowCardinality(String),   -- common to every event; low-card
        destination      LowCardinality(String),   -- frequent filter (Q1, Q5); ORDER BY
        purpose          LowCardinality(String),   -- frequent filter (Q1); ORDER BY
        user_id          String,                   -- common identity; high-card; ORDER BY
        timestamp        DateTime64(3, 'UTC'),      -- event's own timestamp; ORDER BY tail
        flow             LowCardinality(String),    -- hot filter (Q1); skip-indexed
        eta_shown        LowCardinality(String),    -- hot filter (Q2); skip-indexed
        citizenship      LowCardinality(String),    -- hot filter (Q5); skip-indexed
        device_type      LowCardinality(String),    -- hot filter; skip-indexed
        os               LowCardinality(String),    -- hot filter (Nullable in source); skip-indexed
        is_back_filled   Bool                       -- boolean flag (Q4); skip-indexed
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    INDEX idx_flow        payload.flow           TYPE set(10)  GRANULARITY 4,
    INDEX idx_eta_shown   payload.eta_shown      TYPE set(10)  GRANULARITY 4,
    INDEX idx_citizenship payload.citizenship    TYPE set(100) GRANULARITY 4,
    INDEX idx_device_type payload.device_type    TYPE set(20)  GRANULARITY 4,
    INDEX idx_os          payload.os             TYPE set(20)  GRANULARITY 4,
    INDEX idx_back_filled payload.is_back_filled TYPE set(2)   GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.destination, payload.purpose, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

-- ─────────────────────────────────────────────────────────────────────────────
-- Daily rollup of application-start counts by the hot dimensions.
-- Serves Q4 (is_back_filled rate) and Q5 (citizenship x destination volume)
-- directly, and provides the reusable DENOMINATOR for the cross-event
-- conversion / drop-off questions (Q1-Q3), whose numerator events
-- (purchase_completed / document upload) are NOT in this spec's NDJSON.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlys.application_started_daily
(
    day             Date,
    destination     LowCardinality(String),
    purpose         LowCardinality(String),
    flow            LowCardinality(String),
    eta_shown       LowCardinality(String),
    citizenship     LowCardinality(String),
    is_back_filled  Bool,
    applications    AggregateFunction(count),
    unique_users    AggregateFunction(uniq, String),
    agg_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, destination, purpose, flow, eta_shown, citizenship, is_back_filled)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.mv_application_started_daily
TO atlys.application_started_daily
AS
SELECT
    toDate(payload.timestamp)                              AS day,
    CAST(payload.destination AS LowCardinality(String))    AS destination,
    CAST(payload.purpose AS LowCardinality(String))        AS purpose,
    CAST(payload.flow AS LowCardinality(String))           AS flow,
    CAST(payload.eta_shown AS LowCardinality(String))      AS eta_shown,
    CAST(payload.citizenship AS LowCardinality(String))    AS citizenship,
    CAST(payload.is_back_filled AS Bool)                   AS is_back_filled,
    countState()                                           AS applications,
    uniqState(CAST(payload.user_id AS String))             AS unique_users
FROM atlys.application_started
WHERE payload.event = 'application_started'
GROUP BY day, destination, purpose, flow, eta_shown, citizenship, is_back_filled;
