-- ============================================================================
-- 90_reconcile.sql — THE GATE. Recompute concurrency from accepted raw events and compare
-- against the serving layer.
--
-- "Truth" is derived from v_ev_model_input ONLY. It never reads session_intervals or
-- cc_minute_delta, so it exercises the whole pipeline rather than agreeing with
-- itself. It also uses a DIFFERENT implementation of the same spec: runs are
-- detected with window functions where 30_build_intervals.sql uses arraySplit,
-- so an error in either surfaces as a disagreement instead of cancelling out.
--
-- ----------------------------------------------------------------------------
-- REWRITTEN 2026-08-01 after the unseen-day rehearsal found this gate was worth
-- far less than it appeared. Three defects, all now closed:
--
--   1. TARGET MINUTES WERE 2026-07-26 LITERALS. On any other day the query
--      returned ZERO ROWS, and tools/reconcile.sh — which decides by grepping
--      for a mismatch token — found none and printed "reconcile PASSED". A gate
--      that cannot see the data reports success. Minutes are now DERIVED from
--      ev_raw, so the gate re-targets itself on whatever day it is given.
--
--   2. IDLE MINUTES WERE NEVER COMPARED. `truth` was a GROUP BY over a CROSS
--      JOIN, so a minute with nobody watching produced no row and could not
--      disagree. 207 of 1,364 minutes on the holdout day. Proven by inserting
--      500 fabricated viewers at an idle minute: the chart showed 500 and the
--      gate still passed. There is now a dense SPINE of every minute in range,
--      and an idle minute is checked as 0 = 0 like any other.
--
--   3. NOTHING ASSERTED HOW MUCH WAS CHECKED. On a 07-26 day-file the old gate
--      silently returned four rows instead of five. The first output row is now
--      a SUMMARY carrying the number of minutes compared; reconcile.sh fails if
--      that is zero or missing.
--
-- Output is one row set: a SUMMARY row, then every mismatching minute (capped
-- at 20), then five DERIVED sample minutes as human-readable evidence.
-- Any row whose verdict is MISMATCH fails the gate.
-- ============================================================================

WITH
    -- ---- THE POLICY (ADR 0032) ----------------------------------------------
    -- The gate SHARES THE SPEC with sql/30_build_intervals.sql and does NOT
    -- share the implementation — truth below is still derived from ev_raw with
    -- window functions where the model uses arraySplit, so an error in either
    -- surfaces as a disagreement instead of cancelling out.
    --
    -- Until ADR 0032 "shares the spec" meant "carries its own copy of the same
    -- four literals". That copy was the problem: model and gate agreed BY
    -- CONSTRUCTION on the parameter, so `reconcile is green` never meant `the
    -- parameters are right`. Both now read the one declaration in
    -- policy/model.policy, which restores the gate's independence on
    -- everything EXCEPT the parameter and makes the parameter's role explicit
    -- rather than incidental (ADR 0028 item 4).
    --
    -- These constants remain LIVE TRIPWIRES for a spec divergence, and they
    -- have been verified as such: the model at permissive against the gate at
    -- conservative gives 240 mismatched minutes, max_abs_diff 156; the model at
    -- POINT_ACTIVITY_COUNTS=1 against the gate at 0 gives 80 mismatched
    -- minutes, max_abs_diff 16. What changed is that you can no longer create
    -- that divergence by editing one file — you have to edit two builds.
    (SELECT gap_s                     FROM v_model_policy) AS GAP_S,
    (SELECT tail_s                    FROM v_model_policy) AS TAIL_S,
    (SELECT unclosed_pause_to_run_end FROM v_model_policy) AS UNCLOSED_PAUSE_TO_RUN_END,
    (SELECT point_activity_counts     FROM v_model_policy) AS POINT_ACTIVITY_COUNTS,

    -- ---------------------------------------------------------------- truth --
    -- DISTINCT first: the file contains duplicate events at identical
    -- timestamps, and run detection depends only on the SET of instants.
    -- Without this, `prev_ts`/`rn` (ordered by the millisecond timestamp) and
    -- the running sum (ordered by the second-truncated one) resolve ties
    -- differently and run boundaries land in the wrong places.
    distinct_ts AS
    (
        SELECT DISTINCT video_session_id, toUInt32(event_timestamp) AS ts
        FROM v_ev_model_input
    ),
    numbered AS
    (
        SELECT
            video_session_id,
            ts,
            lagInFrame(ts) OVER (PARTITION BY video_session_id ORDER BY ts) AS prev_ts,
            row_number()   OVER (PARTITION BY video_session_id ORDER BY ts) AS rn
        FROM distinct_ts
    ),
    runs AS
    (
        SELECT video_session_id, run_id, min(ts) AS r_start, max(ts) AS r_end,
               arraySort(groupArray(ts)) AS run_ts
        FROM
        (
            SELECT
                video_session_id, ts,
                sum(if((rn = 1) OR ((ts - prev_ts) > GAP_S), 1, 0)) OVER (
                    PARTITION BY video_session_id ORDER BY ts
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS run_id
            FROM numbered
        )
        GROUP BY video_session_id, run_id
    ),
    pauses AS
    (
        SELECT
            video_session_id,
            arraySort(groupArrayIf(toUInt32(event_timestamp), event = 'pause'))  AS ps,
            arraySort(groupArrayIf(toUInt32(event_timestamp), event = 'resume')) AS rs
        FROM v_ev_model_input
        GROUP BY video_session_id
    ),
    windowed AS
    (
        SELECT
            r.video_session_id AS video_session_id,
            r.r_start AS r_start,
            r.r_end   AS r_end,
            r.run_ts  AS run_ts,
            -- `>=` on the resume lookup, MATCHING sql/30_build_intervals.sql.
            -- Timestamps are truncated to whole seconds, so a strict `>` is blind
            -- to a resume landing in the same second as its pause: 2,697 of 27,340
            -- pauses (9.86%). This gate carried the IDENTICAL expression, so it
            -- reproduced the bug and agreed with the model — an independent
            -- implementation of a wrong DEFINITION proves nothing. Like
            -- UNCLOSED_PAUSE_TO_RUN_END above, the SPEC is shared here and the
            -- CODE is not; changing one file without the other is a divergence
            -- this gate will (correctly) fail on. ADR 0009.
            -- The permissive branch's lookup into `run_ts` stays STRICT — the
            -- pause is itself in `run_ts` at p.
            -- Zero-length tie windows dropped, as in the model: they are absorbed
            -- correctly by the fold either way, but they split one interval into
            -- two abutting ones and an interval boundary carries meaning.
            -- A window is HALF-OPEN [p, e): paused p+1 .. e-1, active at p and at
            -- e. So e must be a real active instant — a resume inside the run —
            -- and a pause nothing ever closed ends at r_end + 1 instead, saying
            -- the viewer was still paused at the run's last instant. ADR 0031;
            -- mirrors the arithmetic in sql/30_build_intervals.sql.
            arrayFilter(w -> w.2 > w.1, arraySort(arrayMap(
                p -> (p,
                        if((arrayFirst(x -> x >= p, p2.rs) != 0)
                             AND (arrayFirst(x -> x >= p, p2.rs) <= r.r_end),
                           toUInt32(arrayFirst(x -> x >= p, p2.rs)),
                           if(UNCLOSED_PAUSE_TO_RUN_END = 1,
                              toUInt32(r.r_end + 1),
                              if(arrayFirst(x -> x > p, r.run_ts) = 0,
                                 toUInt32(r.r_end + 1),
                                 toUInt32(arrayFirst(x -> x > p, r.run_ts)))))),
                arrayFilter(p -> (p >= r.r_start) AND (p < r.r_end), p2.ps)
            ))) AS wins
        FROM runs AS r
        LEFT JOIN pauses AS p2 ON p2.video_session_id = r.video_session_id
    ),
    folded AS
    (
        SELECT
            video_session_id, r_start, r_end,
            arrayFold(
                (acc, w) -> (
                    if((w.1 > acc.2) OR ((POINT_ACTIVITY_COUNTS = 1) AND (w.1 = acc.2)),
                       arrayPushBack(acc.1, (acc.2, w.1)), acc.1),
                    greatest(acc.2, w.2)),
                wins,
                (CAST([], 'Array(Tuple(UInt32, UInt32))'), toUInt32(r_start))
            ) AS f
        FROM windowed
    ),
    -- Tail grace ONLY on a segment that ends because the run ended. A segment
    -- ending at a PAUSE gets none — we know to the second when it stopped.
    segments AS
    (
        SELECT
            video_session_id,
            seg.1 AS a,
            seg.2 + if(seg.2 = r_end, TAIL_S, 0) AS b
        FROM folded
        ARRAY JOIN arrayFilter(x -> if(POINT_ACTIVITY_COUNTS = 1, x.2 >= x.1, x.2 > x.1),
                               arrayPushBack(f.1, (f.2, toUInt32(r_end)))) AS seg
    ),
    -- Expanded to minutes ONCE (~147K rows), not CROSS JOINed per target.
    truth_min AS
    (
        SELECT toDateTime(m) AS minute, uniqExact(video_session_id) AS truth
        FROM
        (
            SELECT video_session_id,
                   arrayJoin(range(intDiv(a, 60) * 60, (intDiv(b, 60) * 60) + 1, 60)) AS m
            FROM segments
        )
        GROUP BY minute
    ),

    -- ----------------------------------------------------------------- spine --
    -- Every minute between the first and last event, so an IDLE minute is
    -- compared as 0 = 0 rather than silently skipped. Bounds come from the
    -- data, which is what makes this gate portable to the unseen day.
    bounds AS
    (
        SELECT toStartOfMinute(min(event_timestamp)) AS lo,
               toStartOfMinute(max(event_timestamp)) AS hi
        FROM v_ev_model_input
    ),
    spine AS
    (
        SELECT toDateTime(arrayJoin(range(toUInt32(lo), toUInt32(hi) + 60, 60))) AS minute
        FROM bounds
    ),

    -- --------------------------------------------------------------- served --
    -- Running sum of hour-clipped deltas along the DENSE spine, so the value
    -- carries across minutes where nothing changed. PARTITION BY hour is
    -- mandatory: deltas are hour-clipped (ADR 0003) so each hour is absolute.
    delta_min AS
    (
        SELECT minute, sum(delta) AS d FROM cc_minute_delta GROUP BY minute
    ),
    served AS
    (
        SELECT
            s.minute AS minute,
            toInt64(sum(ifNull(dm.d, 0)) OVER (
                PARTITION BY toStartOfHour(s.minute) ORDER BY s.minute
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )) AS served
        FROM spine AS s
        LEFT JOIN delta_min AS dm ON dm.minute = s.minute
    ),

    compared AS
    (
        SELECT
            sv.minute                                   AS minute,
            toInt64(ifNull(t.truth, 0))                 AS truth,
            sv.served                                   AS served,
            sv.served - toInt64(ifNull(t.truth, 0))     AS diff
        FROM served AS sv
        LEFT JOIN truth_min AS t ON t.minute = sv.minute
    ),

    -- Sample minutes DERIVED from the data: the peak, both boundaries, and two
    -- picked by a stable hash so the choice is reproducible but not cherry-picked.
    samples AS
    (
        SELECT arrayJoin([
            (SELECT argMax(minute, truth) FROM compared),
            (SELECT min(minute) FROM compared),
            (SELECT max(minute) FROM compared),
            (SELECT minute FROM compared ORDER BY cityHash64(minute, 17) LIMIT 1),
            (SELECT minute FROM compared ORDER BY cityHash64(minute, 99) LIMIT 1)
        ]) AS minute
    )

SELECT * FROM
(
    -- 1 — the summary. reconcile.sh fails if minutes_compared is 0 or absent.
    -- `policy` carries the version and content hash of the declaration this
    -- verdict was produced under (ADR 0032), so a pasted gate result is
    -- traceable to a policy without also pasting the tree it came from.
    SELECT
        0 AS ord,
        'SUMMARY' AS scope,
        concat('minutes_compared=', toString(count()))                       AS c1,
        concat('mismatched=', toString(countIf(diff != 0)))                  AS c2,
        concat('max_abs_diff=', toString(max(abs(diff))))                    AS c3,
        concat('peak=', toString(max(truth)))                                AS c4,
        if(countIf(diff != 0) = 0, 'PASS', 'MISMATCH')                       AS verdict,
        concat('policy=v', (SELECT policy_version FROM v_model_policy),
               '/', (SELECT policy_hash FROM v_model_policy))                AS policy
    FROM compared

    UNION ALL

    -- 2 — every disagreeing minute, capped so a total break stays readable.
    SELECT 1, 'MISMATCH', toString(minute), toString(truth), toString(served),
           toString(diff), 'MISMATCH', ''
    FROM compared WHERE diff != 0 ORDER BY abs(diff) DESC LIMIT 20

    UNION ALL

    -- 3 — derived sample minutes, as human-readable evidence.
    SELECT 2, 'sample', toString(c.minute), toString(c.truth), toString(c.served),
           toString(c.diff), if(c.diff = 0, 'PASS', 'MISMATCH'), ''
    FROM compared AS c
    WHERE c.minute IN (SELECT minute FROM samples)
)
ORDER BY ord, c1;
