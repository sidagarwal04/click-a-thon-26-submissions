-- BENCHMARK: the multi-metric minute trend, which is the reason audience_minute_snapshot exists.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- Eight metrics per minute from ONE read of ONE table. The same panel built on the delta tables
-- needs a cumulative sum for sessions, another for users, and four more passes over runs and
-- events for the counts. That is the entire argument for this table, and it is what the read
-- numbers in docs/INSIGHT_BENCHMARKS.md are measuring.
--
-- NOT DENSIFIED HERE, deliberately. serving/concurrency_curve.sql densifies because a curve with
-- gaps produces a wrong average; this query returns the minutes that had an audience and leaves
-- densification to whoever needs a denominator. Adding a bounded WITH FILL would be correct and
-- would also change what the read numbers mean, so the two concerns are kept apart.
--
-- concurrency_deltas REMAINS AUTHORITATIVE. If this table and that one ever disagree, this one
-- is wrong. sql/insights/validation/audience_snapshot_reference.sql asserts they do not, over
-- every minute of the frozen slice, for sessions and users both.
SELECT
    minute,
    toInt64(sum(concurrent_sessions)) AS concurrent_sessions,
    toInt64(sum(concurrent_users))    AS concurrent_users,
    toInt64(sum(session_starts))      AS session_starts,
    toInt64(sum(first_plays))         AS first_plays,
    toInt64(sum(session_ends))        AS session_ends,
    toInt64(sum(background_entries))  AS background_entries,
    toInt64(sum(foreground_entries))  AS foreground_entries,
    toInt64(sum(video_errors))        AS video_errors
FROM
(
    -- Dedupe the ReplacingMergeTree without FINAL, the same pattern the other benchmark uses:
    -- FINAL forces a merge-on-read across the whole selected range, and the filter has already
    -- narrowed it to the rows that matter.
    SELECT
        minute, content_id, platform, country, video_type, app_version,
        argMax(concurrent_sessions, version) AS concurrent_sessions,
        argMax(concurrent_users, version)    AS concurrent_users,
        argMax(session_starts, version)      AS session_starts,
        argMax(first_plays, version)         AS first_plays,
        argMax(session_ends, version)        AS session_ends,
        argMax(background_entries, version)  AS background_entries,
        argMax(foreground_entries, version)  AS foreground_entries,
        argMax(video_errors, version)        AS video_errors
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
ORDER BY minute
-- READ BUDGET. Set from measurement after the fact, never before: the first budget written on
-- session_facts_app_version_health was a guess and failed its own content shape. Fill these from
-- scripts/bench_insights.sh at 3x the worst shape, and recalibrate with that command rather than
-- raising by reflex.
--
-- Unlike the concurrency curve, a time predicate DOES prune here: minute leads this table's
-- ORDER BY, because these rows are absolute values rather than a series that must be summed from
-- its own beginning. That difference is the whole reason the two tables have opposite key orders.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
--
-- RECALIBRATED FOR phoenix_next UNDER LIVE REPLICATION, and the shape of the guard changed with
-- it. The previous ceiling was 3x a measurement taken on a fixed corpus, which is the right guard
-- for a frozen slice and the wrong one here: phoenix_next now takes replicated live data, so the
-- table grows without bound and a multiple of yesterday's size is a ceiling with an expiry date.
-- It expired: this query began failing with TOO_MANY_ROWS at 228,749 rows against a 288,648
-- ceiling while nothing was wrong.
--
-- So the ceiling below is deliberately loose. It catches a full-table regression, a lost prune, a
-- join that fans out, and it no longer certifies a tuned read. The tuned figure is not abandoned,
-- it is conditional: run against the frozen slice and the measurement in the note above still
-- reproduces. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds what a
-- query SCANS and says nothing about how long it may run, which is what the timeouts are for.
SETTINGS max_rows_to_read  = 8000000,
         max_bytes_to_read = 400000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
