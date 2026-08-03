-- SERVING: peak and average concurrency over a range, at any time grain, with filters.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (range, [from, to))
--   grain_s                                    : UInt32  (60 minute, 3600 hour, 86400 day)
--
-- PEAK IS NOT A ROLLUP. It is computed after filtering, from the per-minute series for the
-- exact filter tuple requested, and never read from a stored maximum. An android slice and
-- an android+india slice peak at DIFFERENT MINUTES inside the same range, so a precomputed
-- peak is only ever correct for the slice it was computed for. Asserted by
-- serving/test_peak_is_not_a_rollup.sql, which fails if the two ever agree by construction.
--
-- Grain applies to the reporting bucket, not to the concurrency. Concurrency is always
-- measured per minute; an hour's peak is the maximum of its minutes and an hour's average
-- is the mean of its minutes. Rolling up any other way answers a different question -- the
-- sum of minute peaks, for instance, is not a number that means anything.
--
-- THE AVERAGE DENOMINATOR IS A DEFINITION, AND BOTH ARE REPORTED. Averaging over all
-- minutes in the range (including minutes with zero audience) and averaging over only the
-- minutes that had an audience give materially different answers: 88.2 and 200 over
-- 2026-07-26. avg_all_minutes is primary, being the defensible reading of "average
-- concurrency over a range", but the ground truth is private and a definition mismatch we
-- cannot see is cheap to insure against, so both ship.
--
-- The densification is what makes either of them honest. Deltas exist only at boundary
-- minutes, so an average over the raw rows silently skips every quiet minute. Measured on
-- this data: the previous benchmark query reported 246.98 for a day whose true average is
-- 88.2, a 2.8x over-report, while its peak was correct. Peak escapes the trap because
-- concurrency only changes at a boundary, which is exactly why the bug survived.
WITH filtered AS
(
    SELECT minute, sum(delta) AS d
    FROM concurrency_deltas
    WHERE ({platform:String}    = '' OR platform    = {platform:String})
      AND ({country:String}     = '' OR country     = {country:String})
      AND ({video_type:String}  = '' OR video_type  = {video_type:String})
      AND ({app_version:String} = '' OR app_version = {app_version:String})
      AND ({audio_language:String} = '' OR audio_language = {audio_language:String})
      AND ({subtitle_language:String} = '' OR subtitle_language = {subtitle_language:String})
      AND ({player_version:String} = '' OR player_version = {player_version:String})
      AND ({video_resolution:String} = '' OR video_resolution = {video_resolution:String})
      AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
      AND minute < parseDateTimeBestEffort({to_ts:String})
    GROUP BY minute
),
curve AS
(
    -- Seeded by every delta before the range: a session that opened before from_ts and is
    -- still watching inside it contributes no delta in the range, and would be lost.
    SELECT
        minute,
        toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrency
    FROM filtered
),
seeded_window AS
(
    -- ONE PASS. The obvious way to seed is a separate CTE that re-reads `curve` for the
    -- pre-window rows, but ClickHouse inlines CTEs rather than materialising them, so
    -- referencing `curve` twice scans the delta table twice: measured 53,808 rows read
    -- against a 26,904-row table. Collapsing everything before from_ts into a single group
    -- keyed at from_ts does the same job in one scan and halves the read.
    --
    -- For rows inside the window each minute is its own group and argMax trivially returns
    -- that row. For rows before the window every row lands in the from_ts group and argMax
    -- returns the LAST one, which is precisely the seeded concurrency as of from_ts.
    -- The group key is aliased `m`, NOT `minute`. Aliasing it `minute` shadows curve.minute,
    -- so argMax's key becomes the grouped constant and it returns an arbitrary row instead of
    -- the latest. That is the second time this exact trap bit this file: it silently reported
    -- a seeded concurrency of 1 where the truth was 327, and moved minutes_with_audience from
    -- 635 to 645. Never alias a projection to the name of a column an aggregate still needs.
    SELECT
        if(minute < parseDateTimeBestEffort({from_ts:String}), parseDateTimeBestEffort({from_ts:String}), minute) AS m,
        argMax(concurrency, minute) AS concurrency
    FROM curve
    GROUP BY m
),
dense AS
(
    -- Must complete before any aggregate reads it: WITH FILL runs at ORDER BY time, after
    -- the SELECT list, so aggregating in this same SELECT would aggregate the sparse rows.
    SELECT m AS minute, concurrency
    FROM seeded_window
    ORDER BY minute ASC
    WITH FILL
        FROM parseDateTimeBestEffort({from_ts:String})
        TO   parseDateTimeBestEffort({to_ts:String})
        STEP toIntervalMinute(1)
    INTERPOLATE (concurrency AS concurrency)
)
SELECT
    toStartOfInterval(minute, toIntervalSecond({grain_s:UInt32})) AS bucket,
    max(concurrency)            AS peak_concurrency,
    argMax(minute, concurrency) AS peak_minute,
    round(avg(concurrency), 2)  AS avg_all_minutes,
    -- ifNotFinite guards a bucket with no audience at all: avgIf over zero matching rows
    -- returns nan, and a nan in a dashboard is a bug report waiting to happen.
    ifNotFinite(round(avgIf(concurrency, concurrency > 0), 2), 0) AS avg_active_minutes,
    countIf(concurrency > 0)    AS minutes_with_audience,
    count()                     AS minutes_in_bucket
FROM dense
GROUP BY bucket
ORDER BY bucket
-- READ BUDGET, committed as an assertion rather than a claim in a document.
--
-- WHAT THIS CEILING NOW GUARDS, and what it used to certify. It used to be 3x the frozen
-- slice's worst measured shape: 26,904 rows / 430,464 bytes via scripts/bench.sh (evidence:
-- filter_shapes), on the reasoning that the cumulative sum is seeded by the whole series for
-- the filter tuple, so the read grows with the CORPUS rather than the window, and 3x absorbs
-- a day like that one several times over.
--
-- That premise died when the dashboard's frozen horizon was turned off (frontend/src/lib/env.ts).
-- Against a live stream the corpus is unbounded, so a 3x-of-a-fixed-slice ceiling is not a
-- stale number, it is the wrong SHAPE of guard: measured on the live pipeline, the user curve
-- tripped TOO_MANY_ROWS at 107.58k against 80,712 while nothing was wrong. Recalibrating to
-- 3x-of-current would only reset the clock, roughly three hours at the ~250 delta rows/min
-- this stream writes.
--
-- So the ceiling below is deliberately loose: it catches a FULL-TABLE regression (a lost
-- prune, a re-added second scan of `curve`, a join that fans out) and no longer certifies a
-- tuned read. The tuned figure is not abandoned, it is conditional: run with
-- FROZEN_BEFORE=2026-08-01 and the query reads the same 26,904 rows it always did, which is
-- what reproduces every number in evidence/. Recalibrate the tight figure with
-- scripts/bench.sh against that frozen run, never against a live one.
--
-- force_primary_key is honest but weak here, and the weakness is stated rather than traded
-- on: it passes for EVERY shape, including content-only, because `minute` is itself the last
-- column of the ORDER BY and the range predicate always engages it. It proves the key is
-- used at all; it does not prove the DIMENSION filter pruned. The granule counts in
-- docs/problem/DESIGN.md are what show that, and they show it only for platform.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
SETTINGS max_rows_to_read = 5000000,
         max_bytes_to_read = 80000000,
         force_primary_key = 1,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
