-- =====================================================================
-- 032 — Verification suite for the live path
-- =====================================================================
--
-- Every check states its expected result. Run after 030 (table + MV +
-- backfill). Values marked [sonyliv] are for the 10,866-session CSV
-- extract and will differ on other data; the ASSERTIONS still hold.
--
-- Checks that must pass before the live path is trusted:
--   V1  argMaxIf empty-state merges harmlessly        [VERIFIED]
--   V2  MV agrees with a direct computation           [must be exact]
--   V3  one row per session                           [must be exact]
--   V4  sticky terminated survives late heartbeats    [must be 0 leaks]
--   V5  the chained MV actually fires                 [manual, 1 event]
--   V6  live agrees with the analytics path           [~0 after Part A]
--   V7  the lookback constant is still safe           [must be under 72h]
-- =====================================================================


-- ---------------------------------------------------------------------
-- V1. argMaxIf empty-state merge  [VERIFIED — returns 5]
-- ---------------------------------------------------------------------
-- The whole design rests on this: a block containing only heartbeats
-- produces an EMPTY argMaxIf state, and merging it must NOT clobber an
-- earlier real state — even though the heartbeats are NEWER.
-- If this ever returns 0, the live path is silently wrong and every
-- paused session is being reported as playing.
-- ---------------------------------------------------------------------
SELECT
    argMaxIfMerge(s) AS merged_state,
    argMaxIfMerge(s) = 5 AS pass   -- expect 1
FROM (
    SELECT argMaxIfState(toInt8(5), toDateTime64('2026-08-01 10:01:00',3,'UTC'), toUInt8(1)) AS s
    UNION ALL
    SELECT argMaxIfState(toInt8(0), toDateTime64('2026-08-01 10:05:00',3,'UTC'), toUInt8(0))
    UNION ALL
    SELECT argMaxIfState(toInt8(0), toDateTime64('2026-08-01 10:06:00',3,'UTC'), toUInt8(0))
);


-- ---------------------------------------------------------------------
-- V2. MV agrees with a direct computation over events_clean
-- ---------------------------------------------------------------------
-- Same instant, two routes. MUST be exact — any difference is an MV bug,
-- not rounding. Run at T = now against live traffic.
-- ---------------------------------------------------------------------
WITH now64(3, 'UTC') AS T
SELECT
    mv.live_viewers      AS mv_live,
    direct.live_viewers  AS direct_live,
    mv.live_viewers = direct.live_viewers AS pass   -- expect 1
FROM
(
    SELECT countIf(fg = 1 AND play = 1) AS live_viewers
    FROM (
        SELECT session_key, argMaxIfMerge(fg_state) AS fg, argMaxIfMerge(play_state) AS play
        FROM sonyliv.session_live_now
        WHERE session_start_date >= today() - 3
        GROUP BY session_key
        HAVING max(last_event_ts) > T - INTERVAL 120 SECOND AND max(terminated) = 0)
) AS mv
CROSS JOIN
(
    SELECT countIf(fg = 1 AND play = 1) AS live_viewers
    FROM (
        SELECT session_key,
               maxIf(toUInt8(1), signal = 'session_end') AS terminated,
               max(event_ts) AS last_ts,
               argMaxIf(multiIf(signal IN ('session_end','background'),   toInt8(-1),
                                signal IN ('session_start','foreground'), toInt8(1), toInt8(0)),
                        event_ts,
                        signal IN ('session_end','background','session_start','foreground')) AS fg,
               argMaxIf(multiIf(signal IN ('session_end','error','pause'), toInt8(-1),
                                signal IN ('play','resume'),              toInt8(1), toInt8(0)),
                        event_ts,
                        signal IN ('session_end','error','pause','play','resume')) AS play
        FROM sonyliv.events_clean
        WHERE event_ts <= T
        GROUP BY session_key
        HAVING terminated = 0 AND last_ts > T - INTERVAL 120 SECOND)
) AS direct;

-- Historical anchor, independent of live traffic. Run Q4 in 031 at
-- T = 2026-07-26 10:56:00 — expect live_viewers = 2285,
-- live_incl_paused = 2604.  [sonyliv]


-- ---------------------------------------------------------------------
-- V3. Exactly one logical row per session
-- ---------------------------------------------------------------------
SELECT
    (SELECT uniqExact(session_key) FROM sonyliv.session_live_now)                       AS live_sessions,
    (SELECT uniqExact(session_key) FROM sonyliv.events_clean)                           AS clean_sessions,
    (SELECT uniqExact(session_key) FROM sonyliv.session_live_now)
      = (SELECT uniqExact(session_key) FROM sonyliv.events_clean)                       AS pass;  -- expect 1


-- ---------------------------------------------------------------------
-- V4. Sticky terminated survives post-session_end heartbeats
-- ---------------------------------------------------------------------
-- [sonyliv] 239 sessions emit events AFTER their session_end (2.2% of
-- terminated). This is the case a naive ReplacingMergeTree gets wrong:
-- latest-row-wins would see a heartbeat and resurrect a dead session.
-- Every one of them must report terminated = 1.
-- ---------------------------------------------------------------------
WITH after_end AS (
    SELECT session_key
    FROM sonyliv.events_clean
    GROUP BY session_key
    HAVING maxIf(event_ts, signal = 'session_end') > toDateTime64(0,3,'UTC')
       AND max(event_ts) > maxIf(event_ts, signal = 'session_end')
)
SELECT
    count()                                   AS sessions_with_events_after_end,  -- 239 [sonyliv]
    countIf(l.terminated = 0)                 AS leaked_as_live,                  -- expect 0
    countIf(l.terminated = 0) = 0             AS pass
FROM after_end a
INNER JOIN (
    SELECT session_key, max(terminated) AS terminated
    FROM sonyliv.session_live_now GROUP BY session_key
) l ON l.session_key = a.session_key;


-- ---------------------------------------------------------------------
-- V5. The chained MV actually fires  [MANUAL]
-- ---------------------------------------------------------------------
-- events_clean is itself the target of events_raw_to_clean_mv. An MV on
-- it fires on those inserts — but confirm rather than assume, because a
-- silent failure here means the live number simply stops moving.
--
--   1. Note the current value:
--        SELECT max(last_event_ts) FROM sonyliv.session_live_now;
--   2. Insert one synthetic heartbeat into sonyliv.events_raw for a new
--      session_key, with event_timestamp = now.
--   3. Re-run step 1. The value must advance, and the new session_key
--      must appear in session_live_now.
--
-- If it does not fire, check `deduplicate_blocks_in_dependent_materialized_views`
-- on the loader — the ingest path sets it to 1.
-- ---------------------------------------------------------------------


-- ---------------------------------------------------------------------
-- V6. Live agrees with the analytics path
-- ---------------------------------------------------------------------
-- Compare the live count at an INSTANT against the analytics path
-- evaluated AT THAT SAME INSTANT — never against its minute aggregate.
-- The two measure different things by construction: live answers "who is
-- watching at this moment", the minute grain answers "who watched at any
-- point in this minute". At the peak that is 2285 vs 2728, and neither is
-- wrong.
--
-- After Part A (docs/DECISIONS.md D1 revised, oracle regenerated) both
-- implement solution/policy.yaml, so an instant-to-instant comparison
-- should be ~0. A PERSISTENT non-zero gap is a definition bug, not
-- best-effort slack — that is the whole point of this check.
--
-- VERIFIED on [sonyliv]: at T = 2026-07-26 10:56:00 both sides return
-- exactly 2285. The live path and 011_build_active_intervals.sql already
-- implement the identical definition, and agree with ZERO gap. That is
-- the proof that the reconciliation holds in code — the drift was only
-- ever in the prototype, its oracle, and D1, all fixed in Part A.
--
-- Requires active_intervals to be populated by 011. clip_variant must be
-- pinned or the count doubles (both variants give 2285 here, but relying
-- on that is an accident waiting to happen).
-- ---------------------------------------------------------------------
WITH toDateTime64('2026-07-26 10:56:00', 3, 'UTC') AS T
SELECT
    (SELECT countIf(fg = 1 AND play = 1)
     FROM (
        SELECT session_key,
               maxIf(toUInt8(1), signal='session_end') AS terminated,
               max(event_ts) AS last_ts,
               argMaxIf(multiIf(signal IN ('session_end','background'),   toInt8(-1),
                                signal IN ('session_start','foreground'), toInt8(1), toInt8(0)),
                        event_ts,
                        signal IN ('session_end','background','session_start','foreground')) AS fg,
               argMaxIf(multiIf(signal IN ('session_end','error','pause'), toInt8(-1),
                                signal IN ('play','resume'),              toInt8(1), toInt8(0)),
                        event_ts,
                        signal IN ('session_end','error','pause','play','resume')) AS play
        FROM sonyliv.events_clean WHERE event_ts <= T
        GROUP BY session_key
        HAVING terminated = 0 AND last_ts > T - INTERVAL 120 SECOND)
    )                                                                        AS live_at_T,
    (SELECT uniqExact(session_key) FROM sonyliv.active_intervals
     WHERE policy_version = 'sonyliv-active-v1'
       AND clip_variant   = 'unclipped'
       AND start_time <= T AND end_time > T)                                 AS analytics_at_T;
-- VERIFIED: both return 2285. Any non-zero gap is a definition bug.


-- ---------------------------------------------------------------------
-- V7. The lookback constant is still safe
-- ---------------------------------------------------------------------
-- 031 prunes on `session_start_date >= today() - 3` (72h). If any session
-- spans longer than that, the live query silently under-counts.
-- [sonyliv] max span = 44h.
-- ---------------------------------------------------------------------
SELECT
    max(span_hours)      AS max_session_span_hours,   -- 44 [sonyliv]
    72                   AS lookback_hours,
    max(span_hours) < 72 AS pass                      -- expect 1
FROM (
    SELECT dateDiff('hour', min(event_ts), max(event_ts)) AS span_hours
    FROM sonyliv.events_clean GROUP BY session_key
);
