-- The wrong answer, materialised. Populates concurrency_deltas_naive with the model the
-- problem statement rules out: a session counts as watching for its entire span, first event
-- to last, ignoring background, pause and heartbeat silence.
--
-- Exists so the overcount is a table-vs-table comparison at identical grain, rather than two
-- numbers computed by two different pieces of code that might disagree for reasons other
-- than the thing being measured.
--
-- THE MINUTE-BOUNDARY RULE IS COPIED EXACTLY from the foreground path (02_merge_runs.sql):
--
--   minutes  = timeSlots(start, greatest(dateDiff('second', start, end) - 1, 0), 60)
--   run_end  = last covered minute, INCLUSIVE
--   deltas   = +1 at run_start, -1 at run_end + 1 minute
--
-- The `- 1` second is what stops a span ending exactly on a minute boundary from claiming
-- the minute it never entered. Both sides use it, so any difference between the two tables
-- is the foreground filter and nothing else.
--
-- ONE DELIBERATE ASYMMETRY, and it is the definition of naive, not a bug: the foreground
-- path extends a trailing interval to `last_event + tolerance_s` because a heartbeat is
-- evidence of life for the tolerance window. The naive model has no notion of tolerance, so
-- its span ends at the last event. This makes the naive tail SHORTER, which understates the
-- overcount: the real gap is if anything wider than what this table reports.
--
-- No arraySplit: a naive span is contiguous by construction, so a session is exactly one
-- run. That is the entire error being measured.
--
-- Dimensions come from the session's FIRST event via argMin, identical to
-- 01_derive_intervals.sql, so a session that reports two platforms is filed the same way on
-- both sides and the comparison cannot drift on attribution.
INSERT INTO concurrency_deltas_naive
WITH
    sess AS
    (
        SELECT
            video_session_id,
            min(event_timestamp)                 AS span_start,
            max(event_timestamp)                 AS span_end,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version
        FROM raw_events
        -- Frozen slice, same as every other validated query. Without this the naive table is
        -- built from the corpus PLUS the live stream while the corrected table it is compared
        -- against may not be, and the overcount headline becomes a comparison of two
        -- different datasets.
        WHERE event_timestamp < {frozen_before:String}
        GROUP BY video_session_id
    ),
    runs AS
    (
        SELECT
            s.platform,
            s.country,
            -- LEFT JOIN, matching the foreground path: a session whose content_id is absent
            -- from the catalogue still counts. Dropping it would understate BOTH sides.
            c.video_type AS video_type,
            s.content_id,
            s.app_version,
            toDateTime(toStartOfMinute(s.span_start)) AS run_start,
            toDateTime(toStartOfMinute(s.span_start
                + toIntervalSecond(greatest(dateDiff('second', s.span_start, s.span_end) - 1, 0)))) AS run_end
        FROM sess AS s
        LEFT JOIN content AS c ON s.content_id = c.content_id
    )
SELECT
    platform,
    country,
    video_type,
    content_id,
    app_version,
    d.1 AS minute,
    d.2 AS delta
FROM runs
ARRAY JOIN [(run_start, 1), (run_end + INTERVAL 1 MINUTE, -1)] AS d;
