-- SERVING: exact peak and time-weighted average concurrency over a range, with filters.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (range, [from, to))
--
-- This is the sub-minute companion to peak_average.sql and answers a different question.
-- The minute layer counts a session in every minute it touches, so its peak is "most
-- sessions active within one minute". This query reads instantaneous concurrency: the
-- number of sessions in the foreground at a single point in time, exact to the second the
-- intervals are stored at. exact peak <= minute peak always, because a minute can be
-- touched by two sessions that never coexist.
--
-- THE AVERAGE IS TIME-WEIGHTED, NOT ROW-AVERAGED. Concurrency is a step function that only
-- changes at interval boundaries. Each boundary row holds its value until the next one, so
-- the average over [from, to) is sum(value x seconds held) / window seconds. This is the
-- limit the minute LOCF average approaches as the grain shrinks, computed directly with no
-- densification: quiet time is covered by the denominator, not by generated rows.
--
-- Seeding follows peak_average.sql exactly: every delta before from_ts collapses into one
-- group at from_ts, so a session that opened before the window and is still watching is
-- standing concurrency, not zero. Same one-pass rationale, same aliasing trap (`t`, never
-- `ts`, as the group key).
WITH filtered AS
(
    SELECT ts, sum(delta) AS d
    FROM concurrency_boundary_deltas
    WHERE ({platform:String}    = '' OR platform    = {platform:String})
      AND ({country:String}     = '' OR country     = {country:String})
      AND ({video_type:String}  = '' OR video_type  = {video_type:String})
      AND ({app_version:String} = '' OR app_version = {app_version:String})
      AND ({audio_language:String} = '' OR audio_language = {audio_language:String})
      AND ({subtitle_language:String} = '' OR subtitle_language = {subtitle_language:String})
      AND ({player_version:String} = '' OR player_version = {player_version:String})
      AND ({video_resolution:String} = '' OR video_resolution = {video_resolution:String})
      AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
      AND ts < parseDateTimeBestEffort({to_ts:String})
    GROUP BY ts
),
curve AS
(
    SELECT
        ts,
        toInt64(sum(d) OVER (ORDER BY ts ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrency
    FROM filtered
),
seeded AS
(
    SELECT
        if(ts < parseDateTimeBestEffort({from_ts:String}), parseDateTimeBestEffort({from_ts:String}), ts) AS t,
        argMax(concurrency, ts) AS concurrency
    FROM curve
    GROUP BY t
),
segments AS
(
    -- Each boundary's value holds until the next boundary, or to_ts for the last one.
    -- leadInFrame's default third argument is the type default (epoch), never NULL, so the
    -- window end is passed explicitly.
    SELECT
        t,
        concurrency,
        leadInFrame(t, 1, parseDateTimeBestEffort({to_ts:String})) OVER (
            ORDER BY t ASC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_t
    FROM seeded
),
windowed AS
(
    -- The peak is computed as a window max first so the final aggregate can recover the
    -- FIRST instant it is attained; argMax between equal values is unspecified.
    SELECT
        t,
        concurrency,
        next_t,
        max(concurrency) OVER () AS peak
    FROM segments
    WHERE t < parseDateTimeBestEffort({to_ts:String})
)
SELECT
    max(concurrency)             AS peak_concurrency,
    -- The instant the peak is first reached, exact to the second.
    minIf(t, concurrency = peak) AS peak_at,
    -- Window seconds is the denominator by definition: time before the first boundary and
    -- after the last session closes has concurrency 0 and is covered by the denominator.
    round(sum(concurrency * (next_t - t))
          / (parseDateTimeBestEffort({to_ts:String}) - parseDateTimeBestEffort({from_ts:String})), 2) AS avg_time_weighted,
    ifNotFinite(round(sumIf(concurrency * (next_t - t), concurrency > 0)
          / sumIf(next_t - t, concurrency > 0), 2), 0) AS avg_while_active,
    sumIf(next_t - t, concurrency > 0) AS seconds_with_audience,
    count()                      AS boundaries_in_window
FROM windowed
-- READ BUDGET, same contract as peak_average.sql: measured worst shape, tripled, committed
-- as an assertion. The cumulative sum is seeded by the whole series for the filter tuple,
-- so the read grows with the corpus, not the window; 3x absorbs several days of growth
-- while still catching a full-table regression. Recalibrate with scripts/bench.sh.
-- Measured on the frozen slice: full-table shape reads 79,371 rows / 634,968 bytes in
-- 14 ms (system.query_log, 2026-08-01). Ceilings are 3x that.
SETTINGS max_rows_to_read = 238113,
         max_bytes_to_read = 1904904,
         force_primary_key = 1;
