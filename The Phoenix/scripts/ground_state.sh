#!/usr/bin/env bash
# The frozen-slice metric set. Prints TSV on stdout and writes nothing.
#
#   ./scripts/ground_state.sh
#   FROZEN_BEFORE=2026-08-02 ./scripts/ground_state.sh
#
# Every number here is an aggregate under `< {frozen_before}`. That is not decoration, it
# is the whole design: live ingest is writing into phoenix.raw_events continuously, and a
# metric set that moves between two runs cannot be used to prove anything about anything.
#
# Two rules make the output deterministic, and both were learned by being bitten:
#
#   1. NEVER system.tables.total_rows. Measured 2026-08-01: concurrency_deltas reported
#      34,644 there and 26,904 from count() minutes apart, because background merges were
#      still collapsing rows. total_rows is an estimate that tracks parts, not data.
#
#   2. NEVER a bare count() on a Summing/Collapsing table. count() reads physical rows, and
#      physical rows are a function of merge timing. The stable quantity is the aggregate
#      the engine is maintaining: sum(sign) for Collapsing, sum(delta)/uniqExact(minute)
#      for Summing. Those are what the table MEANS, and they do not move when merges run.
#
# So this script is safe to run while ingest is live, and running it twice must produce
# byte-identical output. scripts/frozen_gate.sh is the thing that proves it does.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${CH_DATABASE:-phoenix}"

CH_DATABASE="$DB" ./scripts/ch.sh --format TSV --query "
SELECT * FROM
(
    -- Volume. raw_events is a plain MergeTree so count() is honest there; every derived
    -- table below reports the aggregate its engine maintains instead.
    SELECT 'rows.raw_events' AS metric, toString(countIf(event_timestamp < {frozen_before:String})) AS value FROM raw_events
    UNION ALL SELECT 'rows.foreground_intervals', toString(countIf(interval_start < {frozen_before:String})) FROM foreground_intervals
    UNION ALL SELECT 'runs.session_minute_runs.asserted', toString(sumIf(sign, run_start < {frozen_before:String})) FROM session_minute_runs
    UNION ALL SELECT 'runs.user_minute_runs.asserted',    toString(sumIf(sign, run_start < {frozen_before:String})) FROM user_minute_runs
    UNION ALL SELECT 'deltas.concurrency_deltas.minutes',      toString(uniqExactIf(minute, minute < {frozen_before:String})) FROM concurrency_deltas
    UNION ALL SELECT 'deltas.user_concurrency_deltas.minutes', toString(uniqExactIf(minute, minute < {frozen_before:String})) FROM user_concurrency_deltas

    -- Cardinality of the corpus itself.
    UNION ALL SELECT 'uniq.sessions', toString(uniqExactIf(video_session_id, event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'uniq.users',    toString(uniqExactIf(user_id,          event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'uniq.contents', toString(uniqExactIf(content_id,       event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'uniq.event_type', toString(uniqExactIf(event_type, event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'uniq.event',      toString(uniqExactIf(event,      event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'span.first_event', toString(minIf(event_timestamp, event_timestamp < {frozen_before:String})) FROM raw_events
    UNION ALL SELECT 'span.last_event',  toString(maxIf(event_timestamp, event_timestamp < {frozen_before:String})) FROM raw_events

    -- Invariants. Each of these is 0 in a correct pipeline; a non-zero is a bug, not a
    -- number to report. Closure (sum of all deltas = 0) says every session that was
    -- counted up was also counted back down.
    UNION ALL SELECT 'invariant.closure.session_deltas', toString(sumIf(delta, minute < {frozen_before:String})) FROM concurrency_deltas
    UNION ALL SELECT 'invariant.closure.user_deltas',    toString(sumIf(delta, minute < {frozen_before:String})) FROM user_concurrency_deltas
    UNION ALL SELECT 'invariant.runs_inverted', toString(countIf(run_end < run_start AND run_start < {frozen_before:String})) FROM session_minute_runs
    UNION ALL SELECT 'invariant.intervals_inverted', toString(countIf(interval_end < interval_start AND interval_start < {frozen_before:String})) FROM foreground_intervals

    -- Zero-length intervals are expected, not a defect, and the count is tracked so nobody
    -- rediscovers them in a review and assumes the worst. foreground_intervals stores
    -- second-resolution DateTime, so a segment shorter than a second collapses to a point.
    -- 42% of intervals are such points. They still contribute exactly one minute, because
    -- timeSlots(t, 0, 60) returns one slot, which is the correct answer: a viewer seen at
    -- 10:00:30 was watching during the 10:00 minute. The invariant that actually matters is
    -- the next one.
    UNION ALL SELECT 'intervals.zero_length', toString(countIf(interval_end = interval_start AND interval_start < {frozen_before:String})) FROM foreground_intervals
    UNION ALL SELECT 'intervals.positive_length', toString(countIf(interval_end > interval_start AND interval_start < {frozen_before:String})) FROM foreground_intervals

    -- THE no-DOUBLE-DERIVE invariant. Must be exactly 1: a given (session, run_start, run_end)
    -- may be asserted once and only once.
    --
    -- This exists because the two invariants that look like they should catch a re-run of the
    -- batch derive both fail to, and that was measured rather than assumed. Running
    -- 02_merge_runs.sql twice doubles every run and takes peak from 2,829 to 5,658, while:
    --
    --   closure (sum(delta) = 0) stays 0, because each duplicated +1 arrives with its own -1;
    --   max_runs_per_session_minute stays 1, because the duplicate has an IDENTICAL key so
    --     GROUP BY collapses it into one group of sum(sign)=2 rather than two overlapping
    --     runs. That invariant detects OVERLAP, and this failure is REPETITION.
    --
    -- Only this one sees it: clean is 1, doubled is 2. Evidence: derive_idempotence.
    UNION ALL SELECT 'invariant.max_assertions_of_one_run', toString(max(s)) FROM
    (
        SELECT sum(sign) AS s FROM session_minute_runs
        WHERE run_start < {frozen_before:String}
        GROUP BY video_session_id, run_start, run_end HAVING s > 0
    )

    -- THE no-double-count invariant. Must be exactly 1: if any session-minute were covered
    -- by two asserted runs, that session would contribute 2 to a count of concurrent
    -- sessions at one instant, which is the single most damaging way this pipeline could be
    -- silently wrong. Cheap to check, so it is checked every run rather than argued about.
    UNION ALL SELECT 'invariant.max_runs_per_session_minute', toString(max(runs_covering)) FROM
    (
        SELECT count() AS runs_covering FROM
        (
            SELECT video_session_id, run_start, run_end FROM session_minute_runs
            WHERE run_start < {frozen_before:String}
            GROUP BY video_session_id, run_start, run_end HAVING sum(sign) > 0
        )
        ARRAY JOIN timeSlots(run_start, toUInt32(dateDiff('second', run_start, run_end)), 60) AS m
        GROUP BY video_session_id, m
    )

    -- The served answer. This is the number the submission quotes, so it belongs in the
    -- gate: if the serving layer moves, the gate fails, whatever the row counts say.
    --
    -- GAP WEIGHTING, and why it is not optional. concurrency_deltas holds one row per
    -- minute where the audience CHANGED, so a cumulative sum over it is a sparse curve:
    -- 1,532 boundary minutes describing a span of 17,027. Concurrency holds flat between
    -- boundaries, so any metric that counts curve ROWS is counting boundaries, not minutes.
    --
    -- Measured: countIf(c > 0) over the sparse rows returns 1,413. The brute-force oracle
    -- over the raw CSV returns 3,664. The gap-weighted figure below returns 3,664 and
    -- agrees with the oracle, which is how we know which one is the metric and which one
    -- was an artifact of the storage layout.
    --
    -- Peak escapes this because concurrency only ever changes at a boundary, so the maximum
    -- over boundaries IS the maximum over minutes. Average and minute-counts do not escape
    -- it. That asymmetry is the whole reason peak_average.sql needs densifying and peak
    -- alone would have looked fine forever.
    UNION ALL SELECT metric, value FROM
    (
        WITH curve AS
        (
            SELECT minute, toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
            FROM (SELECT minute, sum(delta) AS d FROM concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute)
        ),
        held AS
        (
            -- How many minutes this concurrency level holds for, before the next boundary.
            -- The final row is closure (c = 0) so its weight of 0 loses nothing.
            -- greatest(..., 0) guards the final row: leadInFrame has nothing to read past
            -- the end of the frame and returns the DateTime default (the epoch), which
            -- makes the raw dateDiff about -29.7 million minutes and silently destroys any
            -- sum taken over this column. The last boundary is closure (c = 0), so
            -- weighting it 0 is not a patch over the problem, it is the correct weight.
            SELECT c, greatest(dateDiff('minute', minute,
                leadInFrame(minute) OVER (ORDER BY minute ASC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)), 0) AS held_minutes
            FROM curve
        )
        SELECT 'serving.peak_concurrency' AS metric, toString(max(c)) AS value FROM curve
        UNION ALL SELECT 'serving.peak_minute', toString(argMax(minute, c)) FROM curve
        UNION ALL SELECT 'serving.min_concurrency', toString(min(c)) FROM curve
        UNION ALL SELECT 'serving.minutes_with_audience', toString(sumIf(held_minutes, c > 0)) FROM held
        UNION ALL SELECT 'serving.minutes_in_span',      toString(sum(held_minutes)) FROM held
        UNION ALL SELECT 'serving.avg_all_minutes',      toString(round(sum(c * held_minutes) / sum(held_minutes), 2)) FROM held
        UNION ALL SELECT 'serving.avg_active_minutes',   toString(round(sumIf(c * held_minutes, c > 0) / sumIf(held_minutes, c > 0), 2)) FROM held
    )
    UNION ALL SELECT metric, value FROM
    (
        WITH curve AS
        (
            SELECT minute, toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
            FROM (SELECT minute, sum(delta) AS d FROM user_concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute)
        ),
        held AS
        (
            -- greatest(..., 0) guards the final row: leadInFrame has nothing to read past
            -- the end of the frame and returns the DateTime default (the epoch), which
            -- makes the raw dateDiff about -29.7 million minutes and silently destroys any
            -- sum taken over this column. The last boundary is closure (c = 0), so
            -- weighting it 0 is not a patch over the problem, it is the correct weight.
            SELECT c, greatest(dateDiff('minute', minute,
                leadInFrame(minute) OVER (ORDER BY minute ASC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)), 0) AS held_minutes
            FROM curve
        )
        SELECT 'serving.user_peak_concurrency' AS metric, toString(max(c)) AS value FROM curve
        UNION ALL SELECT 'serving.user_peak_minute', toString(argMax(minute, c)) FROM curve
        UNION ALL SELECT 'serving.user_min_concurrency', toString(min(c)) FROM curve
        UNION ALL SELECT 'serving.user_minutes_with_audience', toString(sumIf(held_minutes, c > 0)) FROM held
        UNION ALL SELECT 'serving.user_avg_all_minutes',    toString(round(sum(c * held_minutes) / sum(held_minutes), 2)) FROM held
        UNION ALL SELECT 'serving.user_avg_active_minutes', toString(round(sumIf(c * held_minutes, c > 0) / sumIf(held_minutes, c > 0), 2)) FROM held
    )
)
ORDER BY metric
"
