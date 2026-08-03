-- SERVING: what the pipeline has ingested, for the console's live indicator and for the
-- dashboard's default time window.
--
--
-- THE ONE QUERY THAT DELIBERATELY REPORTS BOTH SIDES OF THE FROZEN BOUNDARY, because it is
-- answering two different questions and conflating them produced a real bug.
--
--   events / latest_event      : the LIVE stream, no frozen predicate. This is the ingest-lag
--                                story: is the pipeline keeping up right now.
--   frozen_earliest / frozen_latest : the bounds of the VALIDATED corpus. The dashboard derives
--                                its default window from these.
--
-- Why they must be separate: every other serving query is frozen to the validated corpus, so a
-- window derived from the live watermark would ask the curve for a range the curve cannot
-- answer, and the dashboard would render an empty chart while reporting a healthy event count.
-- The previous version had only `latest`, taken live, and used it for the window.
--
-- sum(sign) and not count() on the runs tables: they are CollapsingMergeTree, so count() would
-- report asserted plus retracted rows. sum(sign) is the net number of runs currently asserted.
SELECT
    (SELECT count()                FROM raw_events)                                              AS events,
    (SELECT max(event_timestamp)   FROM raw_events)                                              AS latest_event,
    (SELECT min(event_timestamp)   FROM raw_events) AS frozen_earliest,
    (SELECT max(event_timestamp)   FROM raw_events) AS frozen_latest,
    (SELECT sum(sign)              FROM session_minute_runs) AS session_runs,
    (SELECT count()                FROM concurrency_deltas) AS session_deltas,
    (SELECT sum(sign)              FROM user_minute_runs) AS user_runs,
    (SELECT count()                FROM user_concurrency_deltas) AS user_deltas;
