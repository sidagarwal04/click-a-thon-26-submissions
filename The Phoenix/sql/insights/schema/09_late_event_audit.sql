-- INSIGHTS: the lateness exception log.
--
-- Lateness is (arrival_timestamp - event_timestamp). Both are real columns on raw_events as of
-- generation 2, and arrival_timestamp is materialised by raw_events_mv at insert time, so
-- unlike ingested_at it means the same thing every time it is read.
--
-- WHAT THIS TABLE DOES NOT HOLD, and why that is the right shape. It is an EXCEPTION log, not a
-- census: a row lands here only when an event is later than the accepted boundary, or claims to
-- have happened after it arrived. Auditing every on-time event would write one row per raw
-- event, which at the ten-times volume of Stage 5 is nine million rows restating what
-- raw_events already says. The lateness DISTRIBUTION, which is what sizes the boundary, is
-- measured from raw_events directly. See docs/LATENESS.md for that query.
--
-- Consequence, stated so nobody reads a rate out of this table by mistake: a count here is a
-- numerator with no denominator. Divide by the raw_events count over the same window.

CREATE TABLE IF NOT EXISTS late_event_audit
(
    event_date        Date,
    video_session_id  String,
    event_timestamp   DateTime64(3),
    arrival_timestamp DateTime64(3),
    lateness_seconds  Int64,             -- signed: negative means the event is dated in the future
    -- Enum8, not LowCardinality(String), per clickhouse-best-practices rule schema-types-enum:
    -- the four classes are fixed at schema time, so an Enum gets insert-time validation free. A
    -- typo in the classifier below becomes an error at write time instead of a fifth class that
    -- nobody notices in a dashboard. One byte, and the ordering is the severity ordering.
    lateness_class    Enum8('on_time' = 1, 'late_acceptable' = 2,
                            'late_after_finalization' = 3, 'invalid_future_event' = 4),
    event_type        LowCardinality(String),
    event             LowCardinality(String),
    -- Safe here in a way `raw_events.ingested_at` is not: this column exists from the moment the
    -- table is created, so every part is written with the default already evaluated. The
    -- read-time-evaluation trap only catches columns added by ALTER to parts that predate them.
    recorded_at       DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY event_date
-- Class first: every question asked of this table starts by naming a class ("show me everything
-- that landed after finalization"), and the classes are few, so leading with it prunes hardest.
ORDER BY (lateness_class, event_date, video_session_id, event_timestamp);

-- THE BOUNDARIES ARE LITERALS HERE, AND THEY ARE PROVISIONAL.
--
-- A materialized view cannot take query parameters, so the thresholds are written into its body.
-- That is a feature rather than a compromise: it means the enforced policy and the documented
-- policy cannot drift apart silently, because there is exactly one place either can be changed.
-- Recreating the view is a DROP and a CREATE and rewrites no data.
--
-- The values below are NOT measured. Every row in this database arrived by being copied from
-- phoenix, and a copied row has no observed arrival time, so the measurable lateness
-- distribution is currently empty. Sizing a boundary against copied rows would manufacture a
-- zero-lateness distribution and produce exactly the kind of plausible unchecked number that
-- docs/corrections.md exists to catalogue. Stage 5 runs our own ingest and replaces these with
-- measured values. Until then:
--
--   allowed_lateness_seconds  = 90    matches tolerance_s, the gap the state machine already
--                                     treats as the limit of what silence can mean
--   finalization_delay_seconds = 3600 one hour, chosen to exceed any observed batch derive
--                                     cadence, which is the point after which a published
--                                     minute may already have been read by someone
--
-- docs/LATENESS.md carries the same two numbers, the same provisional marker, and the query
-- that will replace them.
CREATE MATERIALIZED VIEW IF NOT EXISTS late_event_audit_mv TO late_event_audit AS
SELECT
    toDate(event_timestamp)                                          AS event_date,
    video_session_id,
    event_timestamp,
    arrival_timestamp,
    dateDiff('second', event_timestamp, arrival_timestamp)           AS lateness_seconds,
    multiIf(
        lateness_seconds < 0,    'invalid_future_event',
        lateness_seconds <= 90,  'on_time',
        lateness_seconds <= 3600,'late_acceptable',
                                 'late_after_finalization')          AS lateness_class,
    event_type,
    event
FROM raw_events
-- arrival_timestamp = 0 is the not-observed sentinel carried by every copied or backfilled row.
-- Those rows did not arrive, so no lateness may be inferred from them and none is.
WHERE arrival_timestamp > toDateTime64(0, 3)
  -- The exception filter. on_time rows are counted from raw_events, not stored here.
  AND (dateDiff('second', event_timestamp, arrival_timestamp) > 90
       OR dateDiff('second', event_timestamp, arrival_timestamp) < 0);
