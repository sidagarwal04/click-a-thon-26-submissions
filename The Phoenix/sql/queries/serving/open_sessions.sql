-- SERVING: sessions that are still open as of a watermark, and how much of their counted
-- time is provisional.
--
--   as_of         : String  (the watermark to evaluate against)
--   tolerance_s   : UInt32  (gap tolerance, 90 to match the pipeline)
--   row_limit     : UInt32  (rows returned; the totals are over ALL open sessions, not the page)
--
-- This answers problem-statement question 5, "how do you handle sessions that are still open,
-- whose active ranges keep growing as new heartbeats arrive", from the serving side. The
-- pipeline side of that answer is retraction, and the proof it works is
-- evidence/open_session_update.
--
-- WHAT "OPEN" MEANS HERE, because the word is ambiguous and the ambiguity matters:
--
--   a session with no VideoSessionEnd, whose last event is at or before the watermark, and
--   which is still inside the gap tolerance at the watermark.
--
-- The third clause is what stops an abandoned session being counted forever. A client that
-- stopped emitting an hour ago is not open, it is gone; it simply never said so. The
-- tolerance is the only thing that distinguishes those two cases, because AppBackgrounded is
-- explicitly not a guaranteed event.
--
-- PROVISIONAL TAIL is the part a reader should look at. Every open session is currently
-- counted through last_event + tolerance, and every one of those seconds may be retracted
-- when the next heartbeat arrives and reveals the session was paused, backgrounded, or
-- finished. It is the size of the answer that is still allowed to change, which is a number
-- worth putting on a dashboard next to a live concurrency figure rather than hiding.
WITH
    parseDateTimeBestEffort({as_of:String}) AS watermark,
    toIntervalSecond({tolerance_s:UInt32})  AS tol,
    per_session AS
    (
        SELECT
            video_session_id,
            argMin(user_id,     event_timestamp) AS user_id,
            argMin(platform,    event_timestamp) AS platform,
            argMin(country,     event_timestamp) AS country,
            argMin(content_id,  event_timestamp) AS content_id,
            max(event_timestamp)                 AS last_event,
            -- countIf rather than a join back: the close events are in the same scan.
            countIf(event_type = 'VideoSessionEnd') AS ends,
            countIf(event_type = 'AppBackgrounded') AS backgrounds
        FROM raw_events
        WHERE event_timestamp <= watermark
        GROUP BY video_session_id
    )
SELECT
    video_session_id,
    user_id,
    platform,
    country,
    content_id,
    last_event,
    -- How far the current answer extends this session beyond its last known event.
    toDateTime(last_event) + tol                                   AS counted_until,
    dateDiff('second', watermark, toDateTime(last_event) + tol)    AS provisional_seconds,
    backgrounds,
    -- TOTALS OVER EVERY OPEN SESSION, not over the returned page. Computed as window functions
    -- so the headline figures survive the LIMIT below: a dashboard that showed "50 open" because
    -- it asked for 50 rows would be reporting its own page size as a measurement. Same reason
    -- the curve query computes peak and average with OVER () before densification is truncated.
    count()                    OVER () AS open_sessions,
    sum(provisional_seconds)   OVER () AS provisional_seconds_total,
    countIf(backgrounds > 0)   OVER () AS open_with_background
FROM per_session
WHERE ends = 0
  AND toDateTime(last_event) + tol > watermark
ORDER BY provisional_seconds DESC, video_session_id
-- Per clickhouse-best-practices rule agent-query-safety: an unbounded row count is not a
-- guardrail even with a scan budget, because the cost of shipping and rendering the result is
-- unbounded too. The open set is naturally large during a live event, so the query pages and
-- the aggregates above carry the full-population answer.
LIMIT {row_limit:UInt32}
-- READ BUDGET. Note the scale difference and why it is expected: this is the ONE serving query
-- that reads raw_events rather than the delta table, because "which sessions are open right now"
-- is a question about events, not about a pre-aggregated curve. It was 905,558 rows and 132 MiB
-- against the curve queries' 26,904 rows and 210 KiB, and the ceiling was 3x that.
--
-- The 3x-of-a-measurement policy died with the frozen horizon (see concurrency_curve.sql):
-- raw_events grows without bound under live ingest, so the ceiling below is a full-table-scan
-- sanity bound rather than a tuned figure. The tight number is reproducible under
-- FROZEN_BEFORE=2026-08-01.
--
-- The scan is a full one BY CONSTRUCTION and that is stated rather than hidden. Per
-- clickhouse-best-practices rule schema-pk-filter-on-orderby, an efficient filter must engage
-- the ORDER BY prefix; raw_events is ordered (video_session_id, event_timestamp) and this query
-- filters on event_timestamp alone, because the question is "which of ALL sessions are open",
-- which names no session. Fixing that would mean a second table keyed by time, which is a real
-- option at 100x and not worth its write cost here.
--
-- That is why this query is NOT on the dashboard refresh path. It is a drill-down: the console
-- runs it on demand, never on the 5-second tick behind the live chart.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
SETTINGS max_rows_to_read = 200000000,
         max_bytes_to_read = 30000000000,
         max_execution_time = 30,
         max_estimated_execution_time = 60,
         timeout_before_checking_execution_speed = 0;
