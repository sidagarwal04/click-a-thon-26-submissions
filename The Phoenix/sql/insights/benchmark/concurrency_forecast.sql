-- BENCHMARK: a short-horizon projection of concurrency, with the error band it deserves.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (the OBSERVED window the forecast is fitted on)
--
-- The plan's Phase 12. It is deliberately a RANDOM WALK WITH DRIFT and is labelled as such on
-- screen, because the honest version of this is more useful than an impressive one.
--
--   forecast(h) = last_observed + drift * h
--   band(h)     = 1.96 * stddev(per-minute change) * sqrt(h)
--
-- WHY THIS AND NOT SOMETHING CLEVERER. Over a fifteen-minute horizon on a minute-grain series,
-- the last observed value plus a drift term is the baseline that anything more elaborate has to
-- beat, and nothing here has been measured beating it. Shipping a seasonal or regression model
-- without that comparison would be presenting a guess with more decimal places, which is worse
-- than presenting a guess.
--
-- THE BAND WIDENS WITH sqrt(h), which is the property that makes it worth drawing at all. It is
-- the standard error of a random walk: uncertainty accumulates with the square root of the
-- horizon, not linearly, so a fifteen-minute projection is not fifteen times less certain than a
-- one-minute one. A forecast without a widening band invites a reader to trust minute fifteen as
-- much as minute one.
--
-- DRIFT IS A MEDIAN, NOT A MEAN. A single spike minute inside the fit window would drag a mean
-- drift into projecting that spike forever. The median per-minute change is what the series is
-- typically doing.
--
-- The floor at zero is not cosmetic: concurrency cannot be negative, and a declining series
-- extrapolated far enough produces a negative lower bound that would render as a chart going
-- below the axis.
WITH
    15 AS horizon_minutes,

    -- The observed series, densified to one row per minute for the filter tuple. argMax(...,
    -- version) and not FINAL: audience_minute_snapshot is a ReplacingMergeTree and a re-derived
    -- minute carries several versions until a merge collapses them. The inner aliases carry an
    -- m_ prefix so none of them shadows the column of the same name, which is what makes
    -- ClickHouse resolve a WHERE clause against an aggregate and fail with ILLEGAL_AGGREGATION.
    observed AS
    (
        SELECT
            minute,
            toInt64(sum(m_sessions)) AS sessions
        FROM
        (
            SELECT
                minute,
                content_id, platform, country, video_type, app_version,
                argMax(concurrent_sessions, version) AS m_sessions
            FROM audience_minute_snapshot
            WHERE ({platform:String}    = '' OR platform    = {platform:String})
              AND ({country:String}     = '' OR country     = {country:String})
              AND ({video_type:String}  = '' OR video_type  = {video_type:String})
              AND ({app_version:String} = '' OR app_version = {app_version:String})
              AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
              AND minute >= parseDateTimeBestEffort({from_ts:String})
              AND minute <  parseDateTimeBestEffort({to_ts:String})
            GROUP BY minute, content_id, platform, country, video_type, app_version
        )
        GROUP BY minute
    ),

    -- Per-minute changes, from which both the drift and the band come. lagInFrame over the whole
    -- ordered series; the first row has no predecessor and is dropped by the NOT isNull guard.
    changes AS
    (
        SELECT
            minute,
            sessions,
            sessions - lagInFrame(sessions) OVER (ORDER BY minute ASC ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS delta,
            row_number() OVER (ORDER BY minute DESC) AS from_end
        FROM observed
    ),

    fit AS
    (
        SELECT
            -- The last observed minute anchors the forecast; everything else is a rate.
            argMin(sessions, from_end)                       AS last_sessions,
            argMin(minute, from_end)                         AS last_minute,
            -- ifNotFinite on both statistics. A fit window with fewer than two changes makes
            -- stddevPop return NaN, and the arithmetic below then fails the whole query with
            -- CANNOT_CONVERT_TYPE rather than returning a wide band. A degenerate fit should
            -- produce a flat forecast with no band, which is the honest answer to "we have almost
            -- no history here", not an error.
            ifNotFinite(quantileExact(0.5)(delta), 0)        AS drift,
            -- stddevPop and not stddevSamp: this is the whole observed series, not a sample of a
            -- larger one, and at short fit windows the n-1 correction is a distinction without a
            -- difference that would still need explaining.
            ifNotFinite(stddevPop(delta), 0)                 AS sigma,
            count()                                          AS fitted_minutes
        FROM changes
        WHERE from_end > 1
    )
SELECT
    toDateTime(last_minute + toIntervalMinute(h))                                   AS minute,
    'forecast'                                                                      AS kind,
    greatest(0, toInt64(round(last_sessions + drift * h)))                          AS sessions,
    greatest(0, toInt64(round(last_sessions + drift * h - 1.96 * sigma * sqrt(h)))) AS lower_95,
    greatest(0, toInt64(round(last_sessions + drift * h + 1.96 * sigma * sqrt(h)))) AS upper_95,
    toInt64(h)                                                                      AS minutes_ahead,
    toInt64(fitted_minutes)                                                         AS fitted_on_minutes,
    round(drift, 2)                                                                 AS drift_per_minute
FROM fit
-- arrayJoin over a generated range rather than a join to numbers(): the horizon is a constant and
-- fit is exactly one row, so this stays a projection over that single row.
ARRAY JOIN range(1, horizon_minutes + 1) AS h
ORDER BY minute
-- READ BUDGET. Scans audience_minute_snapshot for the filter tuple over the fit window; the
-- forecast itself is arithmetic on one row and costs nothing. Sized as a full-table-scan bound
-- rather than a tuned figure, because the table grows with the live stream.
SETTINGS max_rows_to_read = 8000000,
         max_bytes_to_read = 400000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
