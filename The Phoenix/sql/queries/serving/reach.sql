-- SERVING: reach, meaning distinct sessions and distinct users active at ANY point in a
-- window. A different question from concurrency, which asks how many were watching AT ONCE.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- Returns exactly two rows, level = 'sessions' and level = 'users', so the dashboard's
-- compare mode gets both from one round trip instead of two.
--
-- WHY THIS FILE EXISTS RATHER THAN A COLUMN ON concurrency_curve.sql: reach reads the runs
-- tables, not concurrency_deltas. Folding it into the curve query would put a second table
-- behind that query's read budget and break its force_primary_key = 1 assertion (see the
-- budget note at the bottom). Separate access pattern, separate file, separate honest budget.
--
-- HOW A CollapsingMergeTree MUST BE READ, because the dashboard got this exactly backwards.
--
-- The merged PR computed reach with `WHERE sign = 1`, under a comment claiming that "a run's
-- -1 retraction is simply never selected, so a stale +1 is never counted." The reasoning is
-- inverted. Collapsing happens during background merges, on no schedule you control, so in
-- an unmerged part a retracted run has BOTH rows present. `WHERE sign = 1` keeps the stale
-- +1 and discards the -1 that was written to cancel it, which means uniqExact counts
-- precisely the sessions the retraction existed to remove. The error is invisible on a
-- freshly merged table and appears under exactly the condition the retraction model is for:
-- an open session that has been re-derived.
--
-- The correct read is to group by the run's identity and keep it only if the assertions
-- outnumber the retractions. That is the pattern already used at scripts/derive.sh:68
-- (GROUP BY video_session_id, run_start, run_end HAVING sum(sign) > 0), and it is correct
-- whether or not a merge has happened. FINAL would also be correct and is not used here:
-- it forces a merge-on-read across the whole part set, which is the cost this schema was
-- designed to avoid.
WITH
    asserted_sessions AS
    (
        SELECT video_session_id
        FROM session_minute_runs
        WHERE ({platform:String}    = '' OR platform    = {platform:String})
          AND ({country:String}     = '' OR country     = {country:String})
          AND ({video_type:String}  = '' OR video_type  = {video_type:String})
          AND ({app_version:String} = '' OR app_version = {app_version:String})
          AND ({audio_language:String} = '' OR audio_language = {audio_language:String})
          AND ({subtitle_language:String} = '' OR subtitle_language = {subtitle_language:String})
          AND ({player_version:String} = '' OR player_version = {player_version:String})
          AND ({video_resolution:String} = '' OR video_resolution = {video_resolution:String})
          AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
          -- Overlap, not containment: a run that started before the window and is still
          -- running inside it is active in the window. run_end is the last minute the
          -- session is active in, inclusive, so the lower bound is >= and not >.
          AND run_start <  parseDateTimeBestEffort({to_ts:String})
          AND run_end   >= parseDateTimeBestEffort({from_ts:String})
        GROUP BY video_session_id, run_start, run_end
        HAVING sum(sign) > 0
    ),
    asserted_users AS
    (
        SELECT user_id
        FROM user_minute_runs
        WHERE ({platform:String}    = '' OR platform    = {platform:String})
          AND ({country:String}     = '' OR country     = {country:String})
          AND ({video_type:String}  = '' OR video_type  = {video_type:String})
          AND ({app_version:String} = '' OR app_version = {app_version:String})
          AND ({audio_language:String} = '' OR audio_language = {audio_language:String})
          AND ({subtitle_language:String} = '' OR subtitle_language = {subtitle_language:String})
          AND ({player_version:String} = '' OR player_version = {player_version:String})
          AND ({video_resolution:String} = '' OR video_resolution = {video_resolution:String})
          AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
          AND run_start <  parseDateTimeBestEffort({to_ts:String})
          AND run_end   >= parseDateTimeBestEffort({from_ts:String})
        GROUP BY user_id, run_start, run_end
        HAVING sum(sign) > 0
    )
SELECT 'sessions' AS level, uniqExact(video_session_id) AS reach FROM asserted_sessions
UNION ALL
SELECT 'users'    AS level, uniqExact(user_id)          AS reach FROM asserted_users
ORDER BY level
-- READ BUDGET. Measured this session, not estimated: see the ledger row for reach_budget.
--
-- RECALIBRATED 2026-08-01 after a real TOO_MANY_ROWS breach at 330K rows. This query reads
-- PHYSICAL sign rows, and the retract/assert protocol writes -1/+1 pairs on every
-- incremental derive, so the physical row count grows with derive activity until background
-- merges collapse the pairs. Measured today: phoenix 366,638 rows / 14,219,708 bytes,
-- phoenix_next 224,096 / 9,913,988. Ceiling is 3x the worse of the two. If it breaches
-- again, re-measure first; OPTIMIZE TABLE ... FINAL collapses settled pairs and brings the
-- read back down, but the honest ceiling has to fund the un-merged worst case.
--
-- force_primary_key is deliberately ABSENT here, and the absence is the honest answer rather
-- than a gap. Both runs tables are ORDER BY (id, run_start, run_end), so a window predicate
-- on run_start with no id prefix cannot engage the primary key at all: this query scans the
-- runs tables by design. Asserting force_primary_key = 1 would simply fail. Claiming the key
-- prunes here would be worse than admitting it does not.
--
-- That is also why reach is not on the concurrency curve's budget. The curve reads a
-- SummingMergeTree keyed to prune on dimensions; this reads two CollapsingMergeTrees keyed
-- for session lookup. Averaging the two into one ceiling would hide both.
-- max_execution_time is a wall-clock ceiling, and timeout_before_checking_execution_speed = 0 is
-- what makes it one: the default of 10 gives a query ten seconds of grace before the timeout is
-- enforced at all. Per clickhouse-best-practices rule agent-query-safety, a read budget bounds
-- what a query SCANS and says nothing about how long it may run.
SETTINGS max_rows_to_read = 1099914,
         max_bytes_to_read = 42659124,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
