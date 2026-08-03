-- BENCHMARK: what arrived late, how late, and whether it landed after we had already answered.
--
--   from_ts, to_ts : String  (window over event_timestamp, [from, to))
--
-- The plan's Phase 0.4 question. Lateness is the reason the whole pipeline is retractable: a delta
-- table that could not be revised would have to choose between waiting for stragglers and being
-- wrong, and this table is the measure of how often that choice would have come up.
--
-- FOUR CLASSES, and only one of them is a problem.
--
--   on_time                 arrived within the allowed lateness
--   late_acceptable         late, but before its minute was finalized: absorbed with no correction
--   late_after_finalization arrived AFTER its minute was served, so a published number changed
--   invalid_future_event    arrival before the event it describes, which is a clock problem
--
-- late_after_finalization is the count that matters and it is reported per event type, because
-- WHICH event arrived late decides what it changed. A late VideoHeartbeat extends an active range
-- and revises concurrency upward; a late AppBackgrounded retracts counted time and revises it
-- down. Aggregating them into one number would hide the direction of the correction.
--
-- No dimension filters: late_event_audit carries the event and its timing, not the session's
-- platform or country. Joining back to raw_events to get them would put raw_events into this
-- query's plan, which the plan document's Gate B forbids for a serving query. The classes and the
-- event types are what this table can answer, and it answers them off its own ORDER BY prefix.
SELECT
    lateness_class,
    event_type,
    count()                                          AS events,
    uniqExact(video_session_id)                      AS sessions,
    round(avg(lateness_seconds), 1)                  AS avg_lateness_seconds,
    quantileExact(0.95)(lateness_seconds)            AS p95_lateness_seconds,
    max(lateness_seconds)                            AS max_lateness_seconds
FROM late_event_audit
WHERE event_timestamp >= parseDateTimeBestEffort({from_ts:String})
  AND event_timestamp <  parseDateTimeBestEffort({to_ts:String})
-- count() is correct here and nowhere else in this directory: late_event_audit is a plain
-- MergeTree, not Collapsing or Replacing, so a physical row is an event and nothing collapses.
GROUP BY lateness_class, event_type
ORDER BY
    -- The class that changed a published answer sorts first regardless of volume, because it is
    -- read first. Ordering purely by count would bury four corrections under a million on-time
    -- events.
    lateness_class = 'late_after_finalization' DESC,
    events DESC
-- READ BUDGET. Grows with the event stream, since this table takes one row per classified event.
-- Sized as a full-table-scan bound rather than a tuned figure, for the reason
-- sql/queries/serving/concurrency_curve.sql sets out: against a live stream the corpus is
-- unbounded, so a multiple of a fixed measurement is the wrong shape of guard.
SETTINGS max_rows_to_read = 50000000,
         max_bytes_to_read = 4000000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
