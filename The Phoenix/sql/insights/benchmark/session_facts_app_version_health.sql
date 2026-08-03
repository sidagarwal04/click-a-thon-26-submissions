-- BENCHMARK: app-version health and retention, the question session_insight_facts exists for.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- Answers in one read of one table: which app version retains viewers, which one loses them,
-- and whether errors track the difference. Before this table, the same question needed the
-- state machine re-run over raw_events.
--
-- WHY NOT `FINAL`. session_insight_facts is a ReplacingMergeTree, so a re-derived session can
-- have an unmerged superseded row, and reading it raw would count that session twice. FINAL is
-- correct and it forces a merge-on-read across the whole selected range, which is the right
-- trade for a correctness comparison and the wrong one for a dashboard. The inner GROUP BY with
-- argMax(version) collapses each session to its newest row using only the rows the filter
-- already selected. Same answer, no full-range merge.
--
-- The double aggregation is not an accident of style: the inner one dedupes SESSIONS, the outer
-- one aggregates them into VERSIONS. Collapsing the two would average over duplicate rows.
-- THE INNER ALIASES CARRY A sess_ PREFIX, and that is not decoration. Writing
-- `argMax(app_version, version) AS app_version` makes the alias shadow the COLUMN of the same
-- name, and ClickHouse then resolves the WHERE clause against the aggregate and rejects the
-- query with ILLEGAL_AGGREGATION. serving/concurrency_curve.sql carries the same warning after
-- the same trap silently returned a seeded concurrency of 1 where the truth was 327. Here it
-- fails loudly instead of quietly, which is luck rather than design.
SELECT
    sess_app_version                                           AS app_version,
    count()                                                    AS sessions,
    countIf(sess_active_after_1m)                              AS retained_1m,
    countIf(sess_active_after_5m)                              AS retained_5m,
    countIf(sess_active_after_15m)                             AS retained_15m,
    round(100.0 * countIf(sess_active_after_5m)  / greatest(count(), 1), 2) AS retention_5m_pct,
    round(100.0 * countIf(sess_active_after_15m) / greatest(count(), 1), 2) AS retention_15m_pct,
    round(avg(sess_active_seconds), 1)                         AS avg_active_seconds,
    quantileExact(0.5)(sess_active_seconds)                    AS median_active_seconds,
    quantileExact(0.9)(sess_active_seconds)                    AS p90_active_seconds,
    countIf(sess_video_error_count > 0)                        AS sessions_with_error,
    round(100.0 * countIf(sess_video_error_count > 0) / greatest(count(), 1), 2) AS error_session_pct,
    countIf(sess_background_count > 0)                         AS sessions_backgrounded,
    round(100.0 * countIf(sess_foreground_return_count > 0) / greatest(countIf(sess_background_count > 0), 1), 2) AS return_after_background_pct,
    countIf(sess_timed_out)                                    AS timed_out_sessions
FROM
(
    SELECT
        video_session_id,
        argMax(app_version, version) AS sess_app_version,
        argMax(active_seconds, version) AS sess_active_seconds,
        argMax(active_after_1m, version) AS sess_active_after_1m,
        argMax(active_after_5m, version) AS sess_active_after_5m,
        argMax(active_after_15m, version) AS sess_active_after_15m,
        argMax(video_error_count, version) AS sess_video_error_count,
        argMax(background_count, version) AS sess_background_count,
        argMax(foreground_return_count, version) AS sess_foreground_return_count,
        argMax(timed_out, version) AS sess_timed_out
    FROM session_insight_facts
    WHERE ({platform:String}    = '' OR platform    = {platform:String})
      AND ({country:String}     = '' OR country     = {country:String})
      AND ({video_type:String}  = '' OR video_type  = {video_type:String})
      AND ({app_version:String} = '' OR app_version = {app_version:String})
      AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
      AND session_start >= parseDateTimeBestEffort({from_ts:String})
      AND session_start <  parseDateTimeBestEffort({to_ts:String})
    GROUP BY video_session_id
)
GROUP BY sess_app_version
ORDER BY sessions DESC
-- READ BUDGET, committed as an assertion rather than a claim, and set from a MEASUREMENT that
-- corrected a guess. The first version of this file carried a ceiling written before anything
-- was measured, reasoning that the day holds 10,866 sessions. The budget promptly failed the
-- content shape with TOO_MANY_BYTES at 2.14 MiB against a 2.11 MiB ceiling, which is the budget
-- doing its job to its own author. Measured worst shape (evidence:
-- insight_bench_session_facts_app_version_health): content, 10,866 rows, 1,121,645 bytes.
-- Ceilings below are 3x that.
--
-- RE-MEASURED after the ORDER BY change. The previous worst shape was 21,732 rows and 2,243,290
-- bytes, so this looks like a halving, and only part of it is the key: that measurement carried
-- TWO stored versions per session and this one carries one. The clean signal for the key is the
-- granule count, which went from 3 of 3 to 1 of 1. Said plainly because a benchmark that claims
-- a 2x win it did not earn is worse than one that claims nothing.
--
-- WHY 21,732 AND NOT 10,866: STORED VERSIONS. session_insight_facts is a ReplacingMergeTree and
-- the refresh had run twice, so every session had two rows and the inner GROUP BY read both.
-- read_rows therefore scales with versions-per-session until a merge collapses them, and the 3x
-- multiplier is absorbing that as much as it is absorbing data growth. An incremental refresh
-- touches only changed sessions, which is the designed usage; the full refresh measured here is
-- the worst case.
--
-- WHAT THE MEASUREMENT DOES NOT SHOW, stated because a benchmark table is where a reader looks
-- for pruning and would otherwise infer it: the dimension filters DO NOT reduce the read here.
-- Every shape reads ~21.7k rows, and `content` reads MORE bytes than unfiltered, 2,243,290
-- against 2,069,549, because it has to read the content_id column in order to filter on it.
-- The ORDER BY leads with content_id while the query's selective predicate is a session_start
-- range that spans every content_id, so the key cannot prune. At 119,491 rows and 3 granules
-- this is noise, and reordering the key would only move the problem onto content-filtered
-- queries. Left alone deliberately, per the plan's own Phase 14 rule about not making a risky
-- immutable-key migration for a theoretical benefit, and re-measured at ten times volume in
-- Stage 5, which is the point at which it stops being noise.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
--
-- RECALIBRATED FOR phoenix_next UNDER LIVE REPLICATION, and the shape of the guard changed with
-- it. The previous ceiling was 3x a measurement taken on a fixed corpus, which is the right guard
-- for a frozen slice and the wrong one here: phoenix_next now takes replicated live data, so the
-- table grows without bound and a multiple of yesterday's size is a ceiling with an expiry date.
-- It expired: this query began failing with TOO_MANY_ROWS at 134,361 rows against a 32,598
-- ceiling while nothing was wrong.
--
-- So the ceiling below is deliberately loose. It catches a full-table regression, a lost prune, a
-- join that fans out, and it no longer certifies a tuned read. The tuned figure is not abandoned,
-- it is conditional: run against the frozen slice and the measurement in the note above still
-- reproduces. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds what a
-- query SCANS and says nothing about how long it may run, which is what the timeouts are for.
SETTINGS max_rows_to_read  = 5000000,
         max_bytes_to_read = 400000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;