-- BENCHMARK: how sessions move between playback states, and how long they sit in each.
--
--   platform, country, video_type, app_version : String  ('' = all)
--   content_id                                 : Int64   (0  = all)
--   from_ts, to_ts                             : String  (window, [from, to))
--
-- The flow question the plan's Phase 2 exists for: how many sessions backgrounded, how many came
-- back, how many went silent and never returned, and how long each state lasted. One row per
-- observed (from_state, to_state) edge, which is the shape a flow diagram consumes directly.
--
-- SUM(sign), NEVER count(). session_state_transitions is a CollapsingMergeTree, so a session
-- re-derived after a late event carries retraction rows alongside its assertions and count() reads
-- both. On the current corpus that is not a subtlety: the table holds 1,364,784 physical rows and
-- 75,854 asserted ones, so count() overstates by a factor of eighteen.
--
-- The net sum IS the asserted edge count, without a per-row GROUP BY first. Every assertion
-- contributes +1 and its retraction -1, so summing sign over an edge cancels the pairs and leaves
-- exactly the transitions that currently stand. Deduplicating row-by-row before aggregating would
-- give the same answer for eighteen times the work.
--
-- AVERAGE DURATION IS SIGN-WEIGHTED for the same reason. avg(seconds_in_previous_state) would
-- average retracted rows in alongside live ones. sum(seconds * sign) / sum(sign) removes a
-- retracted row's contribution from both the numerator and the denominator, which is the only
-- form of the average that survives a re-derive.
--
-- ZERO-DURATION EDGES ARE REAL AND KEPT. A VideoPlay immediately followed by an AppBackgrounded in
-- the same second is a viewer who opened the app and left, and it is one of the more interesting
-- rows on this table rather than noise to filter out.
--
-- THE SESSION COUNT NEEDS THE INNER GROUP BY, and this is the trap that makes the whole file
-- two-level. sum(sign) is retraction-safe because assertions and retractions cancel numerically.
-- uniqExact(video_session_id) is NOT: a session id appears on both its assertion and its
-- retraction, and a distinct count has no way to cancel them, so a session whose edge was
-- retracted still counts as having taken it. Measured on the current corpus: the
-- stale_heartbeat -> playing_foreground edge reported 3,405 transitions and 7,038 sessions, more
-- sessions than transitions, which is impossible and is the signature of exactly this mistake.
--
-- So the inner query nets each (edge, session) pair first. Then a pair that still stands has
-- net > 0 and a pair that was retracted has net = 0, and both aggregates fall out of the same
-- pass: transitions is the sum of the nets, sessions is the count of pairs that survived.
--
-- AND max() IS NOT RETRACTION-SAFE EITHER, which the Gate A diff against
-- validation/state_flow_ground_truth.sql caught after the session count was already fixed. A plain
-- max(seconds_in_previous_state) reports the longest duration among ALL physical rows including
-- retracted ones: measured 1,134 seconds on the background -> ended edge against a true 168. Every
-- other column agreed, so nothing about the result looked wrong.
--
-- The fix is the innermost GROUP BY, which nets by DURATION as well as by session. Each distinct
-- duration then cancels its own retraction, so maxIf(..., net > 0) one level up sees only the
-- durations that still stand. A live transition and a retracted one sharing a duration still net
-- positive, which is correct: that duration does survive.
--
-- Three levels rather than the full-row dedup the reference uses, which is the trade: exact, and
-- still grouping by four columns instead of fifteen.
SELECT
    from_state,
    to_state,
    toInt64(sum(session_net))                                       AS transitions,
    toInt64(countIf(session_net > 0))                               AS sessions,
    -- greatest(..., 1) guards the divide when an edge's assertions and retractions cancel exactly,
    -- which happens for an edge that existed and no longer does.
    round(sum(session_weighted) / greatest(sum(session_net), 1), 1) AS avg_seconds_in_from_state,
    toInt64(max(session_max))                                       AS max_seconds_in_from_state,
    -- Synthesised transitions carry an event type that cannot appear in raw_events, so this counts
    -- the edges entered by silence rather than by an observed event.
    toInt64(sum(session_timeout))                                   AS entered_by_timeout
FROM
(
    SELECT
        from_state,
        to_state,
        video_session_id,
        sum(net)                        AS session_net,
        sum(weighted_seconds)           AS session_weighted,
        -- maxIf over the SURVIVING durations only. This is the level the duration grouping below
        -- exists to make possible.
        maxIf(seconds_in_previous_state, net > 0) AS session_max,
        sum(net_timeout)                AS session_timeout
    FROM
    (
        SELECT
            from_state,
            to_state,
            video_session_id,
            seconds_in_previous_state,
            sum(sign)                                            AS net,
            sum(seconds_in_previous_state * sign)                AS weighted_seconds,
            sumIf(sign, trigger_event_type = 'HeartbeatTimeout') AS net_timeout
        FROM session_state_transitions
        WHERE ({platform:String}    = '' OR platform    = {platform:String})
          AND ({country:String}     = '' OR country     = {country:String})
          AND ({video_type:String}  = '' OR video_type  = {video_type:String})
          AND ({app_version:String} = '' OR app_version = {app_version:String})
          AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
          AND transition_at >= parseDateTimeBestEffort({from_ts:String})
          AND transition_at <  parseDateTimeBestEffort({to_ts:String})
        GROUP BY from_state, to_state, video_session_id, seconds_in_previous_state
    )
    GROUP BY from_state, to_state, video_session_id
)
GROUP BY from_state, to_state
-- An edge whose assertions and retractions cancel to zero no longer exists and must not be drawn.
HAVING transitions > 0
ORDER BY transitions DESC
-- READ BUDGET. Measured against the physical row count rather than the asserted one, because that
-- is what the scan actually touches: 1,364,784 rows on the current corpus. The ceiling below is
-- roughly 3x, which absorbs both data growth and the retraction rows a re-derive adds before a
-- merge collapses them. Per clickhouse-best-practices rule agent-query-safety a read budget bounds
-- what a query SCANS and says nothing about how long it may run, which is what the two timeout
-- settings are for; timeout_before_checking_execution_speed = 0 is what makes max_execution_time a
-- wall-clock limit rather than a limit with ten seconds of grace.
--
-- No force_primary_key, and the reason is worth stating rather than leaving as an omission. The
-- table's ORDER BY is (video_session_id, playback_instance_no, transition_at, transition_sequence),
-- which is a per-session lookup key: video_session_id leads at 119,495 distinct values, so a query
-- that asks about a time range across all sessions engages nothing. Every predicate this file
-- carries is a range or a dimension, so it full-scans by construction. That is a property of the
-- key rather than of this query, it is why the budget below is sized against the whole table, and
-- it is the first thing to revisit if this view gets slow at ten times the volume.
-- RESIZED against the live table rather than the frozen corpus it was first written for. The
-- budget was 4.2M rows, which the table itself passed at 2.21M today, so the console's
-- "everything derived" range failed with "Limit for rows to read exceeded" the moment live ingest
-- pushed a full-range scan past it. A guard that fires on the honest query rather than on the
-- runaway one teaches a reader to raise it without looking, which is worse than no guard.
-- Sized at roughly 4x the current table so it still catches a join that fans out, and it is a
-- CEILING, not a target: the measured read for a one-day window is 576,093 rows.
SETTINGS max_rows_to_read = 9000000,
         max_bytes_to_read = 820000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
