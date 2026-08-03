-- ============================================================================
-- 40_deltas.sql — H3. session_intervals -> cc_minute_delta, hour-clipped.
--
-- Per ADR 0003, every interval is clipped to each hour it touches:
--   +1 at greatest(toStartOfMinute(s), H)
--   -1 at toStartOfMinute(e) + 1 minute, ONLY if the interval ends inside H
-- An interval surviving past H emits no close; hour H+1 re-opens it with a
-- fresh +1. Every hour's running sum is therefore absolute, so a range query
-- never scans from t=0 and partition pruning is exact rather than nominal.
--
-- EDGE CASE the ADR's rule does not state, handled here: if the interval ends
-- in the LAST minute of the hour, toStartOfMinute(e)+60 equals the next hour's
-- start, so the -1 would land in hour H+1 — which has no matching +1, and its
-- running sum would open at -1. The hour boundary already closes the interval,
-- so that close is simply not emitted.
--
-- Re-runnable: TRUNCATE first (see tools/build-model.sh). Deltas are additive,
-- so a double insert silently doubles every number — there is no dedup here to
-- save you.
--
-- SEVEN DIMENSIONS (ADR 0008). content_id/platform/country used to be the only
-- ones that survived; app_version, audio_language, subtitle_language and
-- player_version now come through too, and title/video_type/category ride free
-- off content_id via dict_content (80_content.sql). Two consequences worth
-- knowing before reading the code:
--
--   * ROW COUNT. Finer grain means more rows, MEASURED 24,951 -> 28,024 (1.12x).
--     It is bounded: this table holds at most one open and one close row per
--     (merged run, hour), so 36,930 rows on this file is the ceiling for ANY
--     number of dimensions. Adding a dimension can only spread rows out inside
--     that ceiling, never multiply past it. This is the property that makes
--     "should work even if the number of dimensions increases" true rather than
--     hopeful, and it is the whole reason the serving layer is deltas and not a
--     per-minute explosion.
--
--   * WHERE THE DIMS ARE ATTACHED. Per MERGED RUN, carried through the
--     arrayFold below — not per session with any(). The merge exists to stop one
--     viewer emitting two +1s in the same minute, so the dimension tuple has to
--     be constant within a merged run or the double count comes straight back.
--     Runs of the same session are minute-disjoint by construction, so different
--     runs MAY carry different tuples: a viewer who switches audio track between
--     two watch bursts is attributed correctly to both.
--     ADR 0012: this is now true of ALL SEVEN. platform, country and content_id
--     were the last three taken with any() over the whole session — the last
--     non-deterministic step in the pipeline — and they now ride the same fold
--     in tail slots .7/.8/.9.
-- ============================================================================

INSERT INTO cc_minute_delta

WITH
-- STEP 1 — merge each session's intervals at MINUTE granularity.
--
-- Without this the model double counts. A session that pauses and resumes
-- inside one minute produces two intervals that both touch that minute, and
-- emitting +1 per interval counts one viewer twice. Measured on the real file:
-- 7,395 (session, minute) pairs across 4,797 sessions — 44% of all sessions —
-- which is what /reconcile caught (556 of 1,903 minutes wrong, max diff 195).
--
-- Concurrency counts VIEWERS, not active fragments. Merging on
-- `next_start_minute <= last_end_minute + 60` is exactly equivalent in minute
-- coverage to keeping the fragments separate, and emits fewer rows.
--
-- This is an O(intervals) fold, NOT a per-minute expansion — the serving layer
-- stays O(intervals), which is the whole point of the delta model.
--
-- The fold tuple carries the four new dimensions in slots .3-.6. The MERGE
-- PREDICATE and the start/end arithmetic read only .1 and .2 and are byte
-- identical to the three-dimension version, so run boundaries — and therefore
-- every concurrency number — provably cannot move; the tuple only gains labels.
-- When two intervals merge, the run KEEPS THE EARLIER INTERVAL'S dimensions
-- (acc's, not x's): a merged run is one continuous viewing burst and it is
-- attributed to what the viewer was watching when the burst opened. Measured
-- exposure is in ADR 0008.
--
-- toString() on the dimension columns is not cosmetic: groupArray preserves
-- LowCardinality, and arrayFold requires the accumulator's element type to match
-- the source array's exactly, so an Array(Tuple(..., LowCardinality(String)))
-- source against a CAST-ed Array(Tuple(..., String)) accumulator does not
-- type-check.
--
-- ALL SEVEN DIMENSIONS NOW RIDE THE FOLD (ADR 0012). platform, country and
-- content_id used to be taken with any() over the whole session. That was the
-- last any() in the pipeline and it was wrong twice over:
--
--   * it is non-deterministic BY CONSTRUCTION. On this file it happens not to
--     vary — measured stable at max_threads 1/8/32 and under forced two-level
--     aggregation, because only 25 of 10,866 sessions carry two platforms and
--     none carries two countries or content_ids, so the groups that could vary
--     fit in one block. The identical query over ev_raw (905,558 rows, the same
--     GROUP BY) returns THREE different answers at those same thread counts.
--     The property that protects us here is the input's size, not the code's.
--     ADR 0009 removed any() from the derivation for exactly this reason.
--
--   * it COLLAPSES the per-interval attribution back to one value per session,
--     which is the opposite of what ADR 0008 built. The other four dimensions
--     are already carried PER RUN through this fold; a session that switches
--     platform between two watch bursts was correctly attributed to both for
--     audio_language and wrongly attributed to one for platform.
--
-- The rule is NOT a new mechanism: platform/country/content_id are appended to
-- the fold tuple at the TAIL (slots .7/.8/.9) so the established .1-.6 slots
-- keep their meaning, and they inherit the SAME first-wins-per-run resolution
-- ADR 0008 measured and shipped for the other four. That is precisely the move
-- ADR 0009 made in 30_build_intervals.sql — columns leave the aggregate list,
-- join the existing array at the tail, and reuse the rule already there.
--
-- Run boundaries provably cannot move: the merge predicate and the start/end
-- arithmetic read only .1 and .2, which are untouched. arraySort now orders on
-- a 9-slot tuple instead of 6, which can only break ties among intervals that
-- were already identical in .1-.6 — so the order becomes MORE determined, never
-- less, and two fully identical tuples are interchangeable by definition.
merged AS
(
    SELECT
        video_session_id,
        arrayFold(
            (acc, x) -> if(
                (length(acc.1) = 0) OR (x.1 > (acc.2 + 60)),
                -- disjoint at minute grain: start a new run
                (arrayPushBack(acc.1, x), x.2),
                -- touching or overlapping: extend the run in place, keeping the
                -- run's own start and its own dimension tuple
                (arrayConcat(
                    arraySlice(acc.1, 1, length(acc.1) - 1),
                    [(acc.1[length(acc.1)].1,
                      greatest(acc.2, x.2),
                      acc.1[length(acc.1)].3,
                      acc.1[length(acc.1)].4,
                      acc.1[length(acc.1)].5,
                      acc.1[length(acc.1)].6,
                      acc.1[length(acc.1)].7,
                      acc.1[length(acc.1)].8,
                      acc.1[length(acc.1)].9)]
                 ), greatest(acc.2, x.2))
            ),
            arraySort(groupArray((
                toUInt32(toStartOfMinute(interval_start)),
                toUInt32(toStartOfMinute(interval_end)),
                toString(app_version),
                toString(audio_language),
                toString(subtitle_language),
                toString(player_version),
                toString(platform),
                toString(country),
                content_id
            ))),
            (CAST([], 'Array(Tuple(UInt32, UInt32, String, String, String, String, String, String, Int64))'), toUInt32(0))
        ).1 AS runs
    FROM session_intervals FINAL
    GROUP BY video_session_id
),

-- STEP 2 — clip every merged run to each hour it touches (ADR 0003).
exploded AS
(
    SELECT
        r.7 AS platform,
        r.8 AS country,
        r.9 AS content_id,
        r.3 AS app_version,
        r.4 AS audio_language,
        r.5 AS subtitle_language,
        r.6 AS player_version,
        r.1 AS s,          -- already minute-truncated by the merge
        r.2 AS e,
        arrayJoin(range(
            toUInt32(intDiv(r.1, 3600) * 3600),
            toUInt32(intDiv(r.2, 3600) * 3600) + 1,
            3600
        )) AS h
    FROM merged
    ARRAY JOIN runs AS r
)

SELECT
    minute,
    platform,
    country,
    content_id,
    subtitle_language,
    player_version,
    audio_language,
    app_version,
    sum(d)  AS delta,
    sum(op) AS starts,
    sum(cl) AS ends
FROM
(
    -- OPEN: at the interval's own minute in its first hour, at the hour start
    -- in every subsequent hour.
    SELECT
        toDateTime(greatest(intDiv(s, 60) * 60, h)) AS minute,
        platform, country, content_id,
        subtitle_language, player_version, audio_language, app_version,
        toInt64(1)  AS d,
        toUInt64(1) AS op,
        toUInt64(0) AS cl
    FROM exploded

    UNION ALL

    -- CLOSE: only when the interval genuinely ends inside this hour AND the
    -- close minute is still inside it (see the edge case above).
    SELECT
        toDateTime((intDiv(e, 60) * 60) + 60) AS minute,
        platform, country, content_id,
        subtitle_language, player_version, audio_language, app_version,
        toInt64(-1) AS d,
        toUInt64(0) AS op,
        toUInt64(1) AS cl
    FROM exploded
    WHERE (e < (h + 3600))
      AND (((intDiv(e, 60) * 60) + 60) < (h + 3600))
)
-- Full rebuilds template this final predicate into one explicit set of output
-- dates at a time. The filter belongs after OPEN/CLOSE are derived: filtering
-- source intervals by their start date would lose later days of a long run.
-- The incremental publisher leaves it at 1 and keeps its existing session
-- scope on the load-bearing `FROM session_intervals FINAL` anchor above.
WHERE 1 /* backfill: output dates */
GROUP BY minute, platform, country, content_id,
         subtitle_language, player_version, audio_language, app_version;
