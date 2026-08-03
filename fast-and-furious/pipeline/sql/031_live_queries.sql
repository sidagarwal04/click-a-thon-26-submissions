-- =====================================================================
-- 031 — Live viewership read queries
-- =====================================================================
--
-- Reads sonyliv.session_live_now (see 030). Definition: solution/policy.yaml.
--
-- ---------------------------------------------------------------------
-- THE LOOKBACK CONSTANT
-- ---------------------------------------------------------------------
-- Every query below prunes with `session_start_date >= today() - 3`.
--
-- This is a real hazard, not boilerplate: session_live_now is PARTITIONED
-- BY session_start_date — the session's START, not its event time. A
-- session that started before the window but is STILL EMITTING would be
-- missed entirely, and it would be missed SILENTLY: the query returns a
-- plausible number that is simply too low.
--
-- Measured longest session span in `sonyliv`: 44 hours. A 2-day lookback
-- (48h) leaves only 4h of margin, so this uses 3 days (72h). That also
-- matches the table's 3-day TTL, so there is nothing older to scan and
-- the wider window costs nothing.
--
-- If session durations grow past 72h, this must grow with them, and the
-- TTL in 030 must grow first. Asserted by V7 in 032.
--
-- ---------------------------------------------------------------------
-- NEVER use FINAL on this table
-- ---------------------------------------------------------------------
-- It is an AggregatingMergeTree. Read with GROUP BY + -Merge functions,
-- as below. FINAL would be both wrong-shaped and expensive.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. Live viewers, total
-- ---------------------------------------------------------------------
-- Emits TWO series. `live_viewers` is the served number (policy.yaml:
-- foreground AND playing). `live_incl_paused` is the permissive reading.
--
-- Both are computed because the problem statement is not fully
-- self-consistent about pause and the answer key is sealed — see
-- docs/DECISIONS.md D1. The second countIf runs over rows already
-- scanned, so it is free, and it keeps the pause decision continuously
-- visible instead of buried inside a predicate.
-- ---------------------------------------------------------------------
SELECT
    countIf(fg = 1 AND play = 1) AS live_viewers,
    countIf(fg = 1)              AS live_incl_paused
FROM (
    SELECT
        session_key,
        argMaxIfMerge(fg_state)   AS fg,
        argMaxIfMerge(play_state) AS play
    FROM sonyliv.session_live_now
    WHERE session_start_date >= today() - 3
    GROUP BY session_key
    HAVING max(last_event_ts) > now64(3, 'UTC') - INTERVAL 120 SECOND
       AND max(terminated) = 0
);


-- ---------------------------------------------------------------------
-- Q2. Live viewers by platform
-- ---------------------------------------------------------------------
SELECT
    platform,
    countIf(fg = 1 AND play = 1) AS live_viewers,
    countIf(fg = 1)              AS live_incl_paused
FROM (
    SELECT
        session_key,
        argMaxIfMerge(fg_state)   AS fg,
        argMaxIfMerge(play_state) AS play,
        argMinMerge(platform)     AS platform
    FROM sonyliv.session_live_now
    WHERE session_start_date >= today() - 3
    GROUP BY session_key
    HAVING max(last_event_ts) > now64(3, 'UTC') - INTERVAL 120 SECOND
       AND max(terminated) = 0
)
GROUP BY platform
ORDER BY live_viewers DESC;


-- ---------------------------------------------------------------------
-- Q3. Live viewers by content, top 20, enriched
-- ---------------------------------------------------------------------
-- dictGet is applied AFTER aggregation, on ~20 rows, so it never sits in
-- a filter predicate over a large scan.
-- ---------------------------------------------------------------------
SELECT
    content_id,
    dictGetOrDefault(sonyliv.content_dict, 'title',      tuple(content_id), '(unknown)') AS title,
    dictGetOrDefault(sonyliv.content_dict, 'video_type', tuple(content_id), 'unknown')   AS video_type,
    countIf(fg = 1 AND play = 1) AS live_viewers
FROM (
    SELECT
        session_key,
        argMaxIfMerge(fg_state)   AS fg,
        argMaxIfMerge(play_state) AS play,
        argMinMerge(content_id)   AS content_id
    FROM sonyliv.session_live_now
    WHERE session_start_date >= today() - 3
    GROUP BY session_key
    HAVING max(last_event_ts) > now64(3, 'UTC') - INTERVAL 120 SECOND
       AND max(terminated) = 0
)
GROUP BY content_id
ORDER BY live_viewers DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- Q4. Historical replay — REFERENCE IMPLEMENTATION, reads events_clean
-- ---------------------------------------------------------------------
-- session_live_now CANNOT answer historical questions. Its aggregates
-- have already folded in every event, including events after any T you
-- might ask about, so `max(last_event_ts)` is the session's final
-- timestamp and not its timestamp as of T. Filtering the aggregated
-- table by T silently drops every session that survived past T — which
-- is most of them at a peak minute.
--
-- Historical replay therefore goes back to events_clean with
-- `WHERE event_ts <= T`. This is the reference computation that V2 in
-- 032 compares the MV against at T = now.
--
-- At T = 2026-07-26 10:56:00 on the CSV extract this returns
-- live_viewers = 2285, live_incl_paused = 2604.
--
-- Do NOT compare 2285 against the minute-grain oracle's 2728. Both
-- implement policy.yaml; they differ only in minute attribution — this
-- evaluates an INSTANT, the oracle evaluates a whole minute under a
-- permissive wholly-contained-minute rule. See prototype/reference/README.md.
-- ---------------------------------------------------------------------
WITH toDateTime64('2026-07-26 10:56:00', 3, 'UTC') AS T
SELECT
    countIf(fg = 1 AND play = 1) AS live_viewers,
    countIf(fg = 1)              AS live_incl_paused
FROM (
    SELECT
        session_key,
        maxIf(toUInt8(1), signal = 'session_end') AS terminated,
        max(event_ts)                             AS last_ts,
        argMaxIf(
            multiIf(signal IN ('session_end', 'background'),   toInt8(-1),
                    signal IN ('session_start', 'foreground'), toInt8(1),
                    toInt8(0)),
            event_ts,
            signal IN ('session_end', 'background', 'session_start', 'foreground')) AS fg,
        argMaxIf(
            multiIf(signal IN ('session_end', 'error', 'pause'), toInt8(-1),
                    signal IN ('play', 'resume'),               toInt8(1),
                    toInt8(0)),
            event_ts,
            signal IN ('session_end', 'error', 'pause', 'play', 'resume'))          AS play
    FROM sonyliv.events_clean
    WHERE event_ts <= T
    GROUP BY session_key
    HAVING terminated = 0
       AND last_ts > T - INTERVAL 120 SECOND
);
