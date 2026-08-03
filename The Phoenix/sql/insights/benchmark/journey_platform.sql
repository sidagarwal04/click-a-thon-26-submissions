-- BENCHMARK: which devices hand off to which, and how much of the multi-device traffic is one
-- person moving rather than two screens running at once.
--
--   platform       : String  ('' = all; matches EITHER side of the move)
--   content_id     : Int64   (0 = all)
--   from_ts, to_ts : String  (window over transition_at, [from, to))
--
-- The plan's Phase 7 question, and it is a capacity question rather than a curiosity. If a
-- measurable share of viewers start on a phone and finish on a TV, phone concurrency and TV
-- concurrency are not two independent audiences to provision for: each one's peak includes some of
-- the same person, and the sum overstates the hardware needed.
--
-- HANDOFF AND PARALLEL ARE THE SAME SHAPE UNTIL YOU CHECK OVERLAP, which is why they are counted
-- apart here. On the current corpus 81 of 141 device transitions are `parallel_multi_device`, so
-- 57 percent of what a naive "user changed platform" query would call a handoff is actually two
-- screens running together. A migration report built on that number would be wrong by more than it
-- was right.
--
-- avg overlap is reported alongside, because it separates a clean handoff from a viewer who simply
-- left one device playing to an empty room: a two-second overlap is a person picking up a phone, a
-- twenty-minute overlap is an abandoned screen still counted as an audience.
SELECT
    t_from_platform AS from_platform,
    t_to_platform   AS to_platform,
    toInt64(count())                                            AS moves,
    toInt64(uniqExact(user_id))                                 AS users,
    toInt64(countIf(t_type = 'handoff'))                        AS handoffs,
    toInt64(countIf(t_type = 'parallel_multi_device'))          AS parallel_viewing,
    toInt64(countIf(t_type = 'return_to_previous_device'))      AS came_back,
    round(100.0 * countIf(t_type = 'handoff') / greatest(count(), 1), 1) AS handoff_share_pct,
    quantileExact(0.5)(t_gap)                                   AS median_gap_seconds,
    round(avg(t_overlap), 1)                                    AS avg_overlap_seconds
FROM
(
    SELECT
        user_id,
        to_session_id,
        -- t_ PREFIX ON EVERY INNER ALIAS. Writing `argMax(from_platform, version) AS from_platform`
        -- makes the alias shadow the COLUMN of the same name, and ClickHouse then resolves this
        -- query's own WHERE clause against the aggregate and rejects it with ILLEGAL_AGGREGATION.
        -- That is the third time this exact trap has fired in this codebase: it is also documented
        -- in serving/concurrency_curve.sql, where it did NOT fail loudly and instead returned a
        -- seeded concurrency of 1 against a true 327.
        argMax(from_platform, version)     AS t_from_platform,
        argMax(to_platform, version)       AS t_to_platform,
        argMax(transition_type, version)   AS t_type,
        argMax(gap_seconds, version)       AS t_gap,
        argMax(overlap_seconds, version)   AS t_overlap
    FROM user_platform_transitions
    WHERE ({platform:String} = '' OR from_platform = {platform:String} OR to_platform = {platform:String})
      AND ({content_id:Int64} = 0 OR content_id = {content_id:Int64})
      AND transition_at >= parseDateTimeBestEffort({from_ts:String})
      AND transition_at <  parseDateTimeBestEffort({to_ts:String})
    GROUP BY user_id, to_session_id
)
GROUP BY t_from_platform, t_to_platform
ORDER BY moves DESC
LIMIT 200
-- READ BUDGET, a full-table-scan bound for the same reason as journey_content.sql: this table
-- grows with the stream, so a multiple of a fixed measurement would be a ceiling with an expiry
-- date.
SETTINGS max_rows_to_read = 20000000,
         max_bytes_to_read = 2000000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
