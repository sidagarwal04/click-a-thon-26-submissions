-- BENCHMARK: playback health per minute. "Was the drop technical, or was it the content?"
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- Rates are recomputed from summed counts over summed active sessions, never averaged from the
-- stored per-row rates: averaging a rate across dimension tuples weights a tuple with three
-- active sessions the same as one with three thousand.
--
-- The output is a correlation, and the column names say so. A minute where errors rise and
-- concurrency falls is two series moving together; proving the affected viewers are the ones who
-- left needs session-level linkage that this table does not carry, and the plan's Phase 8 gate
-- says to label it as correlated impact until it does.
-- Inner aliases carry a prefix so they cannot shadow the outer aggregate's own output
-- names. Without it ClickHouse resolves sum(active_sessions) against the alias declared
-- one line above and rejects the query with ILLEGAL_AGGREGATION. Third time this exact
-- shadowing has bitten in this repo; serving/concurrency_curve.sql documents the first,
-- where it did not raise an error and silently returned the wrong number instead.
SELECT
    minute,
    toInt64(sum(h_active))            AS active_sessions,
    toInt64(sum(h_err))       AS video_error_sessions,
    toInt64(sum(h_timeout)) AS heartbeat_timeout_sessions,
    toInt64(sum(h_aband))         AS abandoned_sessions,
    round(100.0 * sum(h_err)       / greatest(sum(h_active), 1), 3) AS video_error_pct,
    round(100.0 * sum(h_timeout) / greatest(sum(h_active), 1), 3) AS timeout_pct,
    round(100.0 * sum(h_aband)         / greatest(sum(h_active), 1), 3) AS abandonment_pct
FROM
(
    SELECT
        minute, content_id, platform, country, app_version, video_type,
        argMax(active_sessions, version) AS h_active,
        argMax(video_error_sessions, version) AS h_err,
        argMax(heartbeat_timeout_sessions, version) AS h_timeout,
        argMax(abandoned_sessions, version) AS h_aband
    FROM playback_health_minute
    WHERE ({platform:String}    = '' OR platform    = {platform:String})
      AND ({country:String}     = '' OR country     = {country:String})
      AND ({video_type:String}  = '' OR video_type  = {video_type:String})
      AND ({app_version:String} = '' OR app_version = {app_version:String})
      AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
      AND minute >= parseDateTimeBestEffort({from_ts:String})
      AND minute <  parseDateTimeBestEffort({to_ts:String})
    GROUP BY minute, content_id, platform, country, app_version, video_type
)
GROUP BY minute
HAVING active_sessions > 0
ORDER BY minute
-- READ BUDGET, set from measurement (evidence: insight_bench_health_incident_window): worst
-- shape 96,217 rows and 2,706,740 bytes. Ceilings are 3x. The previous figure, 192,434 rows,
-- was two stored versions of the same data, not twice the data.
--
-- The most expensive query here, and the reason is visible in the row count: the health table
-- carries a row for every minute a dimension tuple was active, whether or not anything went
-- wrong, so its cardinality tracks the minute snapshot rather than the incident count. Storing
-- only troubled minutes would make this query cheap and the abandonment RATE unanswerable,
-- because the denominator would be gone. Keep the rows, and revisit at Stage 5 volume.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
--
-- RECALIBRATED FOR phoenix_next UNDER LIVE REPLICATION, and the shape of the guard changed with
-- it. The previous ceiling was 3x a measurement taken on a fixed corpus, which is the right guard
-- for a frozen slice and the wrong one here: phoenix_next now takes replicated live data, so the
-- table grows without bound and a multiple of yesterday's size is a ceiling with an expiry date.
-- It expired: this query began failing with TOO_MANY_ROWS at 228,762 rows against a 288,651
-- ceiling while nothing was wrong.
--
-- So the ceiling below is deliberately loose. It catches a full-table regression, a lost prune, a
-- join that fans out, and it no longer certifies a tuned read. The tuned figure is not abandoned,
-- it is conditional: run against the frozen slice and the measurement in the note above still
-- reproduces. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds what a
-- query SCANS and says nothing about how long it may run, which is what the timeouts are for.
SETTINGS max_rows_to_read  = 8000000,
         max_bytes_to_read = 250000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
