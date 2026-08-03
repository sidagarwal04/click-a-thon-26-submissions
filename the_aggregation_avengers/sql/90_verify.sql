-- ===========================================================================
-- 90_verify.sql — read-only. Run after the pipeline, on any day.
-- ===========================================================================
-- Every check here holds on the PROVIDED day and must also hold on the unseen
-- one. Nothing asserts a specific number: hard-coding 2,882 would turn a
-- correct run on different data into a failure. What is asserted is the set of
-- INVARIANTS the design depends on — if one of these breaks, an answer
-- computed downstream is wrong, whatever the number says.
--
-- Run it through scripts/run_pipeline.mjs so the results land in a trace:
--   scripts/run_pipeline.mjs sql/90_verify.sql
-- Safe to run any number of times; it writes nothing.

-- 1. ROW COMPLETENESS ------------------------------------------------------
-- Silver is one row per bronze row, by contract. Any drift means a correction
-- deleted something it was only supposed to flag.
SELECT
    'row_completeness'                                      AS check,
    (SELECT count() FROM bronze_events)                     AS bronze_rows,
    (SELECT count() FROM silver_events)                     AS silver_rows,
    if((SELECT count() FROM bronze_events) = (SELECT count() FROM silver_events),
       'PASS', 'FAIL — silver must be row-complete')        AS verdict;

-- 2. THE MODEL ASSUMPTION ---------------------------------------------------
-- Minute-presence counts a minute only if it contains a heartbeat. The risk is
-- a minute of GENUINE viewing that happens to contain no beat: that minute is
-- dropped, and CCU is understated silently -- no error, just a smaller number.
--
-- The obvious check is heartbeat cadence ("beats faster than 60s, so no active
-- minute can be empty"). THAT CHECK IS WRONG HERE, and it is worth saying why,
-- because it reads as convincing:
--   * one beat instant emits SEVERAL rows (network-activity, buffer-health,
--     video-resize at the same millisecond), so row-to-row gaps are mostly 0s
--     and any percentile computed over them is meaningless;
--   * beatless minutes exist anyway -- 47,008 of them, 25.7% of all the minutes
--     sessions span. A cadence percentile cannot see them at all.
--
-- So measure the failure mode directly: is a beatless minute ever a VIEWING
-- minute? On the provided day, every one of the 5,701 gaps opens in a minute
-- that also carries an explicit `pause` or `AppBackgrounded`. The user stopped
-- watching; the pipeline is right to stop counting. Minute-presence does not
-- approximate foreground viewing here -- it coincides with it.
--
-- If this drops below 100% on a new day, there are gaps nobody asked for, and
-- CCU for those minutes is understated.
WITH holes AS (
    SELECT video_session_id,
           prev_m                                          AS hole_start,
           dateDiff('minute', prev_m, event_minute) - 1     AS len
    FROM (
        SELECT video_session_id, event_minute,
               lagInFrame(toNullable(event_minute), 1, NULL) OVER (
                   PARTITION BY video_session_id ORDER BY event_minute
                   ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
               ) AS prev_m
        -- DISTINCT first: several rows share one beat instant, and without this
        -- every multi-row beat looks like a zero-length gap.
        FROM (SELECT DISTINCT video_session_id, event_minute
              FROM silver_events WHERE is_heartbeat = 1 AND is_duplicate = 0)
    )
    WHERE prev_m IS NOT NULL AND dateDiff('minute', prev_m, event_minute) - 1 > 0
),
stopped AS (
    SELECT DISTINCT video_session_id, event_minute
    FROM silver_events WHERE event IN ('pause', 'AppBackgrounded')
)
SELECT
    'beatless_minutes_explained'                            AS check,
    count()                                                 AS gaps,
    sum(len)                                                AS gap_minutes,
    countIf(s.event_minute IS NULL)                         AS unexplained_gaps,
    sumIf(len, s.event_minute IS NULL)                      AS unexplained_minutes,
    if(countIf(s.event_minute IS NULL) = 0,
       'PASS — every beatless minute follows an explicit stop',
       'FAIL — beatless minutes with no stop signal: CCU is UNDERSTATED for them') AS verdict
FROM holes h
LEFT JOIN stopped s
  ON s.video_session_id = h.video_session_id AND s.event_minute = h.hole_start;

-- 3. GOLD AGREES WITH SILVER ----------------------------------------------
-- The serving layer must return exactly what a direct silver query returns.
-- This is the check that would catch a broken MV, a stale backfill, or a
-- double-inserted backfill — the failure modes that produce a plausible-looking
-- wrong answer rather than an error.
SELECT
    'gold_matches_silver'                                   AS check,
    gold.peak                                               AS gold_peak,
    silver.peak                                             AS silver_peak,
    if(gold.peak = silver.peak, 'PASS', 'FAIL — serving layer disagrees with source') AS verdict
FROM
    (SELECT max(c) AS peak FROM (
        SELECT minute, uniqExactMerge(sessions) AS c FROM gold_ccu_minute GROUP BY minute
     )) AS gold,
    (SELECT max(c) AS peak FROM (
        SELECT event_minute, uniqExact(video_session_id) AS c
        FROM silver_events WHERE is_heartbeat = 1 AND is_duplicate = 0
        GROUP BY event_minute
     )) AS silver;

-- 4. NO SESSION SPANS TWO DIMENSION VALUES THAT ARE MEANT TO BE PINNED -----
-- platform/user_id/content_id are pinned per session in silver. If any session
-- still shows more than one value, the pinning did not run — and the gold
-- design assumes disjoint session sets for those dimensions.
SELECT
    'session_dims_pinned'                                   AS check,
    countIf(platforms > 1)                                  AS split_platform,
    countIf(users > 1)                                      AS split_user,
    countIf(contents > 1)                                   AS split_content,
    if(countIf(platforms > 1) + countIf(users > 1) + countIf(contents > 1) = 0,
       'PASS', 'FAIL — pinning did not apply')              AS verdict
FROM (
    SELECT video_session_id,
           uniqExact(platform)   AS platforms,
           uniqExact(user_id)    AS users,
           uniqExact(content_id) AS contents
    FROM silver_events GROUP BY video_session_id
);

-- 5. THE HEADLINE ----------------------------------------------------------
-- Reported, not asserted: this is the answer, and on a new day it is a new
-- number. Peak is max() over the series, never a stored aggregate.
SELECT
    'headline'                                              AS check,
    max(ccu)                                                AS peak_ccu,
    argMax(minute, ccu)                                     AS peak_minute,
    round(avg(ccu), 2)                                      AS avg_ccu,
    sum(ccu)                                                AS watch_minutes,
    count()                                                 AS minutes_covered
FROM (
    SELECT minute, uniqExactMerge(sessions) AS ccu
    FROM gold_ccu_minute GROUP BY minute
);
