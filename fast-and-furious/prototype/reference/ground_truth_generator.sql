-- =====================================================================
-- Ground truth: foreground-AND-PLAYING concurrency per minute
-- =====================================================================
--
-- Supersedes ground_truth_generator.py, which cannot run:
--   * chdb is not installed
--   * it hardcodes os.chdir('/private/tmp/claude-501/-Users-dahiya-Work-sonyliv/...'),
--     a scratchpad from a different machine that does not exist
--   * it reads raw_events.parquet, which is not in the repo
--
-- This version runs against ClickHouse (Cloud or local) on the canonical
-- normalized table `events_clean`, so it is reproducible by anyone with
-- credentials and works unchanged on the unseen day.
--
-- ---------------------------------------------------------------------
-- DEFINITION (see solution/policy.yaml — the single source of truth)
-- ---------------------------------------------------------------------
-- A (session, minute) pair is active when ALL hold:
--   1. LIVENESS  — a qualifying event occurred in (M-120s, M].
--                  Encoded as: each event covers [m0, m0+60, m0+120],
--                  clipped to the session's own [m_first, m_last].
--   2. FOREGROUND — the minute is NOT wholly inside an
--                  AppBackgrounded -> AppForegrounded window.
--   3. PLAYING   — the minute is NOT wholly inside a
--                  pause|error -> play|resume window.
--
-- Condition 3 is NEW. The previous oracle had no playback axis at all,
-- which is why it disagreed with pipeline/sql/011_build_active_intervals.sql
-- (that file has always gated on playing_state = 1).
--
-- Rationale for excluding paused time, from the problem statement:
--   PS 18: "count only truly active PLAYBACK intervals" — a paused player
--          has no playback.
--   PS 12: "backgrounded, PAUSED, or silent with no heartbeat. Counting
--          that time overstates the audience."
--   PS 31: the dataset ships "playback-state markers (playing, PAUSED,
--          backgrounded, foregrounded)" — they exist to be used.
--
-- ---------------------------------------------------------------------
-- VERIFIED
-- ---------------------------------------------------------------------
-- Disabling excl_pause below reproduces the previous oracle EXACTLY:
--   2970 @ 1785063360 (10:56 UTC), 2965 @ 10:59, 2940 @ 10:58
-- matching prototype/RESULTS.md. The translation is therefore faithful and
-- the only semantic change is the playback axis.
--
-- With the playback axis, on the 10,866-session CSV extract in `sonyliv`:
--   10:56 -> 2728 (was 2970, -8.1%)
--   10:57 -> 2699 (was 2939)
--   10:58 -> 2677 (was 2940)
--   10:59 -> 2691 (was 2965)
--
-- The -8.1% is smaller than an instantaneous evaluation of the same
-- definition (which gives 2285) because the wholly-contained-minute rule
-- is permissive: a pause shorter than a minute boundary excludes nothing.
-- Both are "foreground and playing"; they differ only in minute
-- attribution. Do not compare them directly.
--
-- ---------------------------------------------------------------------
-- CLICKHOUSE FOOTGUN, do not "simplify" this back
-- ---------------------------------------------------------------------
-- The exclusions use  (sk, m) NOT IN (SELECT sk, m FROM ...)  rather than
-- LEFT ANTI JOIN ... ON c.sk = x.sk AND c.m = x.m.
-- A multi-column ON mis-binds across inlined CTEs here and silently
-- over-excludes: measured 149,543 cover pairs minus 46,925 exclusions
-- yielding 13,600 rows instead of 102,618, collapsing the peak from 2,970
-- to 207. The tuple form is correct.
--
-- ---------------------------------------------------------------------
-- USAGE
-- ---------------------------------------------------------------------
--   clickhouse-client --host <host> --port 9440 --secure \
--     --user default --password "$CLICKHOUSE_PASSWORD" \
--     --database sonyliv --queries-file ground_truth_generator.sql
--
-- Swap {db} if the target database is not `sonyliv`.
-- =====================================================================

WITH
ev AS (
    SELECT
        session_key,
        event_type,
        signal,
        toInt64(toUnixTimestamp64Milli(event_ts))                             AS ts,
        intDiv(intDiv(toInt64(toUnixTimestamp64Milli(event_ts)), 1000), 60)*60 AS m0
    FROM sonyliv.events_clean
),

-- Session span, in whole minutes. Bounds every window below.
sess AS (
    SELECT session_key, min(m0) AS m_first, max(m0) AS m_last
    FROM ev GROUP BY session_key
),

-- (1) LIVENESS. VideoHeartbeat covers pause/resume too, which is
-- intentional: those still prove the app is alive. State is handled by
-- the exclusions, not by the liveness set.
cover AS (
    SELECT DISTINCT e.session_key AS sk, e.mm AS m
    FROM (
        SELECT session_key, arrayJoin([m0, m0 + 60, m0 + 120]) AS mm
        FROM ev
        WHERE event_type IN ('VideoSessionStart','VideoPlay','VideoHeartbeat','AppForegrounded')
    ) e
    INNER JOIN sess s ON s.session_key = e.session_key
    WHERE e.mm >= s.m_first AND e.mm <= s.m_last
),

-- (2) FOREGROUND. Minutes wholly inside AppBackgrounded -> AppForegrounded.
-- m_lo rounds UP to the next minute boundary, m_hi rounds DOWN, so a window
-- only excludes minutes it wholly contains.
wb AS (
    SELECT session_key, ts AS b, event_type,
           minIf(ts, event_type = 'AppForegrounded') OVER (
               PARTITION BY session_key ORDER BY ts
               ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS nxt
    FROM ev
    WHERE event_type IN ('AppBackgrounded','AppForegrounded')
),
excl_bg AS (
    SELECT DISTINCT sk, toInt64(arrayJoin(range(toUInt64(m_lo), toUInt64(m_hi) + 60, 60))) AS m
    FROM (
        SELECT wb.session_key AS sk,
               greatest(intDiv(intDiv(wb.b, 1000) + 59, 60)*60, s.m_first) AS m_lo,
               -- nxt = 0 means the session never came back: exclude to session end.
               least(intDiv(intDiv(if(wb.nxt = 0, toInt64(9000000000000), wb.nxt), 1000) - 60, 60)*60,
                     s.m_last) AS m_hi
        FROM wb INNER JOIN sess s ON s.session_key = wb.session_key
        WHERE wb.event_type = 'AppBackgrounded'
    )
    WHERE m_lo <= m_hi
),

-- (3) PLAYING. Same shape as (2), over pause|error -> play|resume.
-- Mirrors playing_setter in pipeline/sql/011_build_active_intervals.sql:
-- stop = {pause, error, session_end}, start = {play, resume}. session_end
-- is omitted here because m_last already bounds every window at it.
-- `error` stops playback but is NOT terminal (policy.yaml error_is_terminal: false).
wp AS (
    SELECT session_key, ts AS b, signal,
           minIf(ts, signal IN ('play','resume')) OVER (
               PARTITION BY session_key ORDER BY ts
               ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS nxt
    FROM ev
    WHERE signal IN ('pause','error','play','resume')
),
excl_pause AS (
    SELECT DISTINCT sk, toInt64(arrayJoin(range(toUInt64(m_lo), toUInt64(m_hi) + 60, 60))) AS m
    FROM (
        SELECT wp.session_key AS sk,
               greatest(intDiv(intDiv(wp.b, 1000) + 59, 60)*60, s.m_first) AS m_lo,
               least(intDiv(intDiv(if(wp.nxt = 0, toInt64(9000000000000), wp.nxt), 1000) - 60, 60)*60,
                     s.m_last) AS m_hi
        FROM wp INNER JOIN sess s ON s.session_key = wp.session_key
        WHERE wp.signal IN ('pause','error')
    )
    WHERE m_lo <= m_hi
),

active AS (
    SELECT sk, m
    FROM cover
    WHERE (sk, m) NOT IN (SELECT sk, m FROM excl_bg)
      AND (sk, m) NOT IN (SELECT sk, m FROM excl_pause)
)

SELECT toUInt32(m) AS minute_ts, toUInt32(count()) AS concurrent_sessions
FROM active
GROUP BY m
ORDER BY m
INTO OUTFILE 'ground_truth_foreground_per_minute.csv' TRUNCATE FORMAT CSVWithNames;
