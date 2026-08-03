-- BENCHMARK: which content takes its audience from which other content, and how much of a title's
-- arrival is cannibalised rather than new.
--
--   content_id     : Int64   (0 = all; matches EITHER side of the move)
--   video_type     : String  ('' = all; the destination's type)
--   from_ts, to_ts : String  (window over transition_at, [from, to))
--
-- The plan's Phase 6 question. Concurrency can show two curves crossing; only this can say whether
-- the same people crossed with them.
--
-- PARALLEL VIEWING IS COUNTED SEPARATELY AND NEVER AS A SWITCH. On the current corpus 882 of 2,403
-- content transitions are `parallel_multi_device`, which is 37 percent: a viewer with the match on
-- the TV and something else on a phone. Folding those into the switch count would overstate
-- cannibalization by more than a third, which is the specific error the plan's acceptance
-- checklist forbids. They are reported in their own column so the reader sees both.
--
-- CANNIBALIZED SHARE is deliberately a share of TRANSITIONS INTO this content, not of all arrivals
-- to it. The denominator for "all viewers joining the new content" lives in
-- audience_minute_snapshot.session_starts, a different table at a different grain, and joining the
-- two here would put a second table in this query's plan for a number the flow view already shows
-- next to it. Stated rather than silently approximated: this column answers "of the people who
-- arrived here FROM somewhere else, how many were genuinely switching".
--
-- argMax(..., version) and not FINAL: user_content_transitions is a ReplacingMergeTree, so a
-- re-derived transition carries several versions until a merge collapses them. The inner GROUP BY
-- collapses each transition to its newest row using only the rows the filter already selected.
-- Same answer, no full-range merge. The inner aliases carry a t_ prefix because an alias that
-- shadows the column of the same name makes ClickHouse resolve the WHERE against the aggregate and
-- fail with ILLEGAL_AGGREGATION; this file hit exactly that during development.
SELECT
    from_title,
    to_title,
    toInt64(count())                                                     AS moves,
    toInt64(uniqExact(user_id))                                          AS users,
    toInt64(countIf(t_type != 'parallel_multi_device'))                  AS real_switches,
    toInt64(countIf(t_type = 'parallel_multi_device'))                   AS parallel_viewing,
    toInt64(countIf(t_type = 'switch_after_end'))                        AS after_it_ended,
    toInt64(countIf(t_type = 'switch_after_background'))                 AS after_backgrounding,
    toInt64(countIf(t_type = 'return_to_previous_content'))              AS came_back,
    round(100.0 * countIf(t_type != 'parallel_multi_device') / greatest(count(), 1), 1) AS switch_share_pct,
    -- Median rather than mean: a single viewer who left a tab open for an hour would drag an
    -- average into meaninglessness, and the question is what a typical move looks like.
    quantileExact(0.5)(t_gap)                                            AS median_gap_seconds
FROM
(
    SELECT
        user_id,
        to_session_id,
        argMax(from_title, version)       AS from_title,
        argMax(to_title, version)         AS to_title,
        argMax(transition_type, version)  AS t_type,
        argMax(gap_seconds, version)      AS t_gap
    FROM user_content_transitions
    WHERE ({content_id:Int64} = 0 OR from_content_id = {content_id:Int64} OR to_content_id = {content_id:Int64})
      AND ({video_type:String} = '' OR to_video_type = {video_type:String})
      AND transition_at >= parseDateTimeBestEffort({from_ts:String})
      AND transition_at <  parseDateTimeBestEffort({to_ts:String})
    GROUP BY user_id, to_session_id
)
GROUP BY from_title, to_title
ORDER BY moves DESC
-- Read from the top: the interesting rows are the biggest flows, and an uncapped list of every
-- content pair any viewer ever moved between is a scroll rather than an answer.
LIMIT 200
-- READ BUDGET, sized as a full-table-scan bound rather than a tuned figure, because this table
-- grows with the live stream. Per clickhouse-best-practices rule agent-query-safety the budget
-- bounds what is SCANNED and the LIMIT bounds what is shipped; neither substitutes for the other.
SETTINGS max_rows_to_read = 20000000,
         max_bytes_to_read = 2000000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
