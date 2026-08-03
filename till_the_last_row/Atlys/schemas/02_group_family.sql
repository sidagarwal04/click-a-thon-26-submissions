-- Schema: 02_group_family
-- Source NDJSON: /app/specs/02_group_family/events.ndjson
-- Database: atlys
-- Base table: group_family  (ONE table per spec — all event types land here)
-- MVs: group_family_daily_mv (-> group_family_daily)
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)

CREATE DATABASE IF NOT EXISTS atlys;

-- ── Base table: one table, all 4 event types ──────────────────────────────
-- event types: group_started, traveller_added, traveller_removed, group_submitted
-- Typed hints cover only ORDER BY paths + skip-indexed/boolean hot filters.
-- Sparse paths (traveller_index, relation, travellers_submitted) are absorbed
-- by the untyped `payload` JSON column.
CREATE TABLE IF NOT EXISTS atlys.group_family
(
    payload JSON(
        event            LowCardinality(String),   -- discriminator; leftmost of key
        application_id   LowCardinality(String),   -- common to all events
        destination      LowCardinality(String),   -- frequent filter (PM Q1/Q4); in key
        user_id          String,                    -- common identity; high-card
        group_size       UInt8,                     -- frequent filter (PM Q1/Q3); in key
        timestamp        DateTime64(3, 'UTC'),      -- event's own timestamp; key tail
        os               LowCardinality(String),    -- hot filter (PM Q4); skip-indexed
        docs_complete    Bool                       -- boolean hot filter (PM Q3); skip-indexed
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    -- data-skipping indexes on hot filters NOT in the ORDER BY:
    INDEX idx_os       payload.os            TYPE set(100)          GRANULARITY 4,
    INDEX idx_docs     payload.docs_complete TYPE set(2)            GRANULARITY 4,
    INDEX idx_group_id CAST(payload.group_id AS String) TYPE bloom_filter(0.01) GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.destination, payload.group_size, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

-- ── Aggregate target for the daily group metrics MV ───────────────────────
CREATE TABLE IF NOT EXISTS atlys.group_family_daily
(
    event_date       Date,
    destination      LowCardinality(String),
    group_size       UInt8,
    groups_started   AggregateFunction(uniq, String),
    groups_submitted AggregateFunction(uniq, String),
    travellers_added_cnt   AggregateFunction(sum, UInt64),
    travellers_removed_cnt AggregateFunction(sum, UInt64),
    docs_incomplete_cnt    AggregateFunction(sum, UInt64),
    docs_added_cnt         AggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, destination, group_size)
TTL event_date + INTERVAL 90 DAY DELETE;

-- ── Incremental MV feeding the daily aggregate ────────────────────────────
-- Serves PM questions:
--   Q1 completion rate  = uniqMerge(groups_submitted)/uniqMerge(groups_started) by group_size
--   Q2 add/remove churn = sumMerge(travellers_added_cnt) vs sumMerge(travellers_removed_cnt)
--   Q3 docs bottleneck  = sumMerge(docs_incomplete_cnt)/sumMerge(docs_added_cnt) by group_size
--   Q4 by destination   = uniqMerge(groups_started) by destination
CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.group_family_daily_mv
TO atlys.group_family_daily
AS
SELECT
    toDate(payload.timestamp)                                        AS event_date,
    payload.destination                                             AS destination,
    CAST(payload.group_size AS UInt8)                               AS group_size,
    uniqIfState(CAST(payload.group_id AS String), payload.event = 'group_started')   AS groups_started,
    uniqIfState(CAST(payload.group_id AS String), payload.event = 'group_submitted') AS groups_submitted,
    sumState(toUInt64(payload.event = 'traveller_added'))           AS travellers_added_cnt,
    sumState(toUInt64(payload.event = 'traveller_removed'))         AS travellers_removed_cnt,
    sumState(toUInt64(payload.event = 'traveller_added' AND payload.docs_complete = false)) AS docs_incomplete_cnt,
    sumState(toUInt64(payload.event = 'traveller_added'))           AS docs_added_cnt
FROM atlys.group_family
GROUP BY event_date, destination, group_size;
