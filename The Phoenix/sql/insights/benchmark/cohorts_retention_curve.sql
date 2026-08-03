-- BENCHMARK: retention by entry cohort. "The audience arrived. Did it stay?"
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- Reads cohort aggregates, never session histories, which is the plan's Phase 5 performance
-- requirement stated as a query. The alternative shape, scanning per-session rows and grouping
-- by entry minute, is what this table exists to avoid.
--
-- Retention is recomputed from the summed COUNTS rather than averaged from the stored ratios.
-- Averaging per-cohort percentages weights a two-session cohort the same as a two-thousand
-- session one, which is a well-known way to publish a retention figure nobody can reproduce.
-- Inner aliases carry a prefix so they cannot shadow the outer aggregate's own output
-- names. Without it ClickHouse resolves sum(entered_sessions) against the alias declared
-- one line above and rejects the query with ILLEGAL_AGGREGATION. Third time this exact
-- shadowing has bitten in this repo; serving/concurrency_curve.sql documents the first,
-- where it did not raise an error and silently returned the wrong number instead.
SELECT
    cohort_minute,
    toInt64(sum(c_entered)) AS entered_sessions,
    round(100.0 * sum(c_a1) / greatest(sum(c_entered), 1), 2) AS retention_1m_pct,
    round(100.0 * sum(c_a5) / greatest(sum(c_entered), 1), 2) AS retention_5m_pct,
    round(100.0 * sum(c_a10) / greatest(sum(c_entered), 1), 2) AS retention_10m_pct,
    round(100.0 * sum(c_a15) / greatest(sum(c_entered), 1), 2) AS retention_15m_pct
FROM
(
    SELECT
        cohort_minute, content_id, platform, country, video_type, app_version,
        argMax(entered_sessions, version) AS c_entered,
        argMax(active_after_1m, version) AS c_a1,
        argMax(active_after_5m, version) AS c_a5,
        argMax(active_after_10m, version) AS c_a10,
        argMax(active_after_15m, version) AS c_a15
    FROM content_entry_cohorts
    WHERE ({platform:String}    = '' OR platform    = {platform:String})
      AND ({country:String}     = '' OR country     = {country:String})
      AND ({video_type:String}  = '' OR video_type  = {video_type:String})
      AND ({app_version:String} = '' OR app_version = {app_version:String})
      AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
      AND cohort_minute >= parseDateTimeBestEffort({from_ts:String})
      AND cohort_minute <  parseDateTimeBestEffort({to_ts:String})
    GROUP BY cohort_minute, content_id, platform, country, video_type, app_version
)
GROUP BY cohort_minute
ORDER BY cohort_minute
-- READ BUDGET, set from measurement (evidence: insight_bench_cohorts_retention_curve): worst
-- shape 8,181 rows and 361,131 bytes on the frozen slice. Ceilings are 3x. Recalibrate with
-- ./scripts/bench_insights.sh, never by raising the number until the error stops.
--
-- The cheapest query in the insight layer by an order of magnitude, and that is the point of
-- the table: one row per cohort minute per tuple instead of one row per session.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
--
-- RECALIBRATED FOR phoenix_next UNDER LIVE REPLICATION, and the shape of the guard changed with
-- it. The previous ceiling was 3x a measurement taken on a fixed corpus, which is the right guard
-- for a frozen slice and the wrong one here: phoenix_next now takes replicated live data, so the
-- table grows without bound and a multiple of yesterday's size is a ceiling with an expiry date.
-- It expired: this query began failing with TOO_MANY_ROWS at 25,497 rows against a 24,543
-- ceiling while nothing was wrong.
--
-- So the ceiling below is deliberately loose. It catches a full-table regression, a lost prune, a
-- join that fans out, and it no longer certifies a tuned read. The tuned figure is not abandoned,
-- it is conditional: run against the frozen slice and the measurement in the note above still
-- reproduces. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds what a
-- query SCANS and says nothing about how long it may run, which is what the timeouts are for.
SETTINGS max_rows_to_read  = 1000000,
         max_bytes_to_read = 60000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
