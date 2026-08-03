-- Schema: 11_document_uploaded
-- Source NDJSON: /app/specs/11_document_uploaded/events.ndjson
-- Database: atlys
-- Base table: document_uploaded  (ONE table per spec — all event types land here)
-- MVs: document_uploaded_daily_agg (via document_uploaded_daily_mv)
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)

CREATE DATABASE IF NOT EXISTS atlys;

CREATE TABLE IF NOT EXISTS atlys.document_uploaded
(
    payload JSON(
        event                                LowCardinality(String),   -- discriminator (single type here); leftmost of key
        application_id                        LowCardinality(String),   -- common to all events; low-card
        doc_type                              LowCardinality(String),   -- frequent filter dim; in ORDER BY
        user_id                               String,                    -- common to all events; high-card
        timestamp                             DateTime64(3, 'UTC'),      -- event's own timestamp
        -- typed ONLY because skip-indexed / boolean hot filters (not in ORDER BY):
        capture_mode                          LowCardinality(String),
        scan_mode                             LowCardinality(String),
        os                                    LowCardinality(String),
        device_type                           LowCardinality(String),
        destination                           LowCardinality(String),
        is_crossed_failed_attempt_threshold   UInt8
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    INDEX idx_capture_mode payload.capture_mode TYPE set(10)  GRANULARITY 4,
    INDEX idx_scan_mode    payload.scan_mode    TYPE set(4)   GRANULARITY 4,
    INDEX idx_os           payload.os           TYPE set(20)  GRANULARITY 4,
    INDEX idx_device_type  payload.device_type  TYPE set(20)  GRANULARITY 4,
    INDEX idx_destination  payload.destination  TYPE set(200) GRANULARITY 4,
    INDEX idx_crossed      payload.is_crossed_failed_attempt_threshold TYPE set(2) GRANULARITY 4,
    INDEX idx_retry        CAST(payload.retry_count AS UInt8) TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.doc_type, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

-- ─────────────────────────────────────────────────────────────────────────────
-- MV: document_uploaded_daily_agg
-- Daily document-upload rollup: upload volume, retry sum, retry avg, threshold-crossings,
-- sliced by doc_type / capture_mode / scan_mode / device_type / os / destination.
-- Serves PM questions 1-4 (retry distribution, threshold share, auto vs manual,
-- iOS vs Android failure). Incremental AggregatingMergeTree.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS atlys.document_uploaded_daily_agg
(
    event_day        Date,
    doc_type         LowCardinality(String),
    capture_mode     LowCardinality(String),
    scan_mode        LowCardinality(String),
    device_type      LowCardinality(String),
    os               LowCardinality(String),
    destination      LowCardinality(String),
    uploads_state             AggregateFunction(count),
    retry_sum_state           AggregateFunction(sum, UInt64),
    retry_avg_state           AggregateFunction(avg, UInt8),
    threshold_crossed_state   AggregateFunction(sum, UInt64),
    agg_insert_time  DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_day)
ORDER BY (event_day, doc_type, capture_mode, scan_mode, device_type, os, destination)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.document_uploaded_daily_mv
TO atlys.document_uploaded_daily_agg
AS
SELECT
    toDate(payload.timestamp)                                  AS event_day,
    COALESCE(CAST(payload.doc_type     AS String), '')         AS doc_type,
    COALESCE(CAST(payload.capture_mode AS String), '')         AS capture_mode,
    COALESCE(CAST(payload.scan_mode    AS String), '')         AS scan_mode,
    COALESCE(CAST(payload.device_type  AS String), '')         AS device_type,
    COALESCE(CAST(payload.os           AS String), '')         AS os,
    COALESCE(CAST(payload.destination  AS String), '')         AS destination,
    countState()                                               AS uploads_state,
    sumState(CAST(payload.retry_count AS UInt64))              AS retry_sum_state,
    avgState(CAST(payload.retry_count AS UInt8))               AS retry_avg_state,
    sumState(CAST(payload.is_crossed_failed_attempt_threshold AS UInt64)) AS threshold_crossed_state
FROM atlys.document_uploaded
WHERE payload.event = 'document_uploaded'
GROUP BY event_day, doc_type, capture_mode, scan_mode, device_type, os, destination;
