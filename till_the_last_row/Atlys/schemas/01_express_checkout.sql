-- Schema: 01_express_checkout
-- Source NDJSON: Atlys/specs/01_express_checkout/events.ndjson
-- Database: atlys
-- Base table: express_checkout  (ONE table per spec — all event types land here)
-- MVs: express_checkout_funnel_hourly, express_payment_latency_hourly
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)
--
-- Best-practices rules applied:
--   schema-json-when-to-use        → single JSON column absorbs all 5 event types
--   schema-pk-cardinality-order    → event (low-card) → application_id (low-card) → destination (low-card) → user_id (high-card) → timestamp (last)
--   schema-pk-prioritize-filters   → Q2 filters: application_id, destination capped at 4-5 cols total
--   schema-types-lowcardinality    → LowCardinality on event, application_id, destination (≤10K distinct values)
--   schema-types-native-types      → DateTime64(3, 'UTC') for timestamps
--   schema-partition-lifecycle     → PARTITION BY toYYYYMMDD(ch_insert_time); TTL 90 days
--   schema-partition-low-cardinality → daily partitions bound partition count

CREATE DATABASE IF NOT EXISTS atlys;

-- ─────────────────────────────────────────────────────────────────────────────
-- Base table: one table for ALL express_checkout event types
-- All 5 event types insert here; the payload JSON column absorbs the union of
-- their fields. Sparse paths (shown_amount, saved_method_type, otp_attempts,
-- payment.*) are EXPECTED to be absent for event types that don't emit them —
-- this is not an error; the untyped payload column absorbs them.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlys.express_checkout
(
    payload JSON(
        event            LowCardinality(String),   -- event-type discriminator; leftmost ORDER BY key
        application_id   LowCardinality(String),   -- frequent filter (Q2); low-cardinality per rule schema-types-lowcardinality
        destination      LowCardinality(String),   -- frequent filter (Q2); country code, low-cardinality
        user_id          String,                   -- high-cardinality identity; no LowCardinality per rule schema-types-lowcardinality
        timestamp        DateTime64(3, 'UTC')      -- event's own timestamp; ORDER BY tail per rule schema-pk-cardinality-order
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
-- ORDER BY: 5 columns — discriminator first, then Q2 frequent filters, user_id, timestamp last
-- rule: schema-pk-cardinality-order (low→high cardinality left→right)
-- channel omitted from key: not present in NDJSON top-level; absorbed as untyped path
ORDER BY (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;


-- ─────────────────────────────────────────────────────────────────────────────
-- MV 1: Funnel event counts per hour × application_id × destination
-- Answers: conversion rate across the 5-step funnel; adoption by dimension
-- Source: reads ALL event types from the base table (no event-type filter needed
--         since we want counts for every step of the funnel)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlys.express_checkout_funnel_hourly
(
    hour             DateTime,
    event_type       LowCardinality(String),
    application_id   LowCardinality(String),
    destination      LowCardinality(String),
    event_count      AggregateFunction(count, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, event_type, application_id, destination)
TTL hour + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.mv_express_checkout_funnel_hourly
TO atlys.express_checkout_funnel_hourly
AS
SELECT
    toStartOfHour(payload.timestamp)    AS hour,
    payload.event                       AS event_type,
    payload.application_id              AS application_id,
    payload.destination                 AS destination,
    countState()                        AS event_count
FROM atlys.express_checkout
GROUP BY hour, event_type, application_id, destination;


-- ─────────────────────────────────────────────────────────────────────────────
-- MV 2: Payment latency quantiles per hour × application_id × destination
-- Answers: p50/p95 payment latency; latency trend over time by destination
-- Source: reads ONLY express_payment_confirmed rows (WHERE payload.event filter)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlys.express_payment_latency_hourly
(
    hour             DateTime,
    application_id   LowCardinality(String),
    destination      LowCardinality(String),
    latency_p50      AggregateFunction(quantile(0.5),  Float64),
    latency_p95      AggregateFunction(quantile(0.95), Float64),
    payment_count    AggregateFunction(count, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, application_id, destination)
TTL hour + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.mv_express_payment_latency_hourly
TO atlys.express_payment_latency_hourly
AS
SELECT
    toStartOfHour(payload.timestamp)              AS hour,
    payload.application_id                        AS application_id,
    payload.destination                           AS destination,
    quantileState(0.5) (payload.payment.latency_ms::Float64)   AS latency_p50,
    quantileState(0.95)(payload.payment.latency_ms::Float64)   AS latency_p95,
    countState()                                  AS payment_count
FROM atlys.express_checkout
WHERE payload.event = 'express_payment_confirmed'
GROUP BY hour, application_id, destination;
