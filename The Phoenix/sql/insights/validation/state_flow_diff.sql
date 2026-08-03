-- DIFF: state_flow.sql (optimized) against state_flow_ground_truth.sql (reference).
--
--   The plan document's Gate A requires this to return:
--     0 differing rows, 0 missing keys, 0 unexpected keys.
--
-- Returns ONE ROW PER DISAGREEMENT and nothing when they agree, which is the shape that makes a
-- pass unambiguous: an empty result is the only passing result, so a query that silently returned
-- nothing for the wrong reason still fails the eye test when its row counts are zero everywhere.
--
-- The `side` column names WHICH implementation is missing a key, because "the two disagree" is not
-- actionable and "the optimized query invented an edge the reference does not have" is.
--
-- FLOAT TOLERANCE. avg_seconds_in_from_state is the only non-integer column. The optimized query
-- computes it as sum(seconds * sign) / sum(net) and the reference as avg(seconds) over the
-- surviving rows; those are the same quantity by different routes, and IEEE754 summation order
-- makes the last digit unstable. 0.05 is half of the one decimal place both sides round to, so any
-- difference this tolerance hides is invisible in the output anyway. Every other column is an
-- exact integer comparison with no tolerance at all.
WITH
    -- MUST MIRROR sql/insights/benchmark/state_flow.sql EXACTLY. ClickHouse cannot include a file,
    -- so the optimized side is copied here, and a copy is a thing that drifts: when this file was
    -- first written it caught a real bug in max_seconds, and then reported the same 10 rows after
    -- the bug was fixed, because only the benchmark had been updated. If this diff fails, check
    -- that the two are still the same query before believing the failure.
    optimized AS
    (
        SELECT
            from_state,
            to_state,
            toInt64(sum(session_net))                                       AS transitions,
            toInt64(countIf(session_net > 0))                               AS sessions,
            round(sum(session_weighted) / greatest(sum(session_net), 1), 1) AS avg_seconds,
            toInt64(max(session_max))                                       AS max_seconds,
            toInt64(sum(session_timeout))                                   AS entered_by_timeout
        FROM
        (
            SELECT
                from_state, to_state, video_session_id,
                sum(net)                                  AS session_net,
                sum(weighted_seconds)                     AS session_weighted,
                maxIf(seconds_in_previous_state, net > 0) AS session_max,
                sum(net_timeout)                          AS session_timeout
            FROM
            (
                SELECT
                    from_state, to_state, video_session_id, seconds_in_previous_state,
                    sum(sign)                                            AS net,
                    sum(seconds_in_previous_state * sign)                AS weighted_seconds,
                    sumIf(sign, trigger_event_type = 'HeartbeatTimeout') AS net_timeout
                FROM session_state_transitions
                WHERE transition_at >= parseDateTimeBestEffort({from_ts:String})
                  AND transition_at <  parseDateTimeBestEffort({to_ts:String})
                  AND transition_at <  {frozen_before:String}
                  AND ({platform:String}    = '' OR platform    = {platform:String})
                  AND ({country:String}     = '' OR country     = {country:String})
                  AND ({video_type:String}  = '' OR video_type  = {video_type:String})
                  AND ({app_version:String} = '' OR app_version = {app_version:String})
                  AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
                GROUP BY from_state, to_state, video_session_id, seconds_in_previous_state
            )
            GROUP BY from_state, to_state, video_session_id
        )
        GROUP BY from_state, to_state
        HAVING transitions > 0
    ),
    reference AS
    (
        SELECT
            from_state,
            to_state,
            toInt64(count())                                          AS transitions,
            toInt64(uniqExact(video_session_id))                      AS sessions,
            round(avg(seconds_in_previous_state), 1)                  AS avg_seconds,
            toInt64(max(seconds_in_previous_state))                   AS max_seconds,
            toInt64(countIf(trigger_event_type = 'HeartbeatTimeout')) AS entered_by_timeout
        FROM
        (
            SELECT
                video_session_id, playback_instance_no, user_id, content_id, platform, country,
                app_version, video_type, transition_at, from_state, to_state, trigger_event_type,
                trigger_event, seconds_in_previous_state, transition_sequence,
                sum(sign) AS net
            FROM session_state_transitions
            WHERE transition_at >= parseDateTimeBestEffort({from_ts:String})
              AND transition_at <  parseDateTimeBestEffort({to_ts:String})
              AND transition_at <  {frozen_before:String}
              AND ({platform:String}    = '' OR platform    = {platform:String})
              AND ({country:String}     = '' OR country     = {country:String})
              AND ({video_type:String}  = '' OR video_type  = {video_type:String})
              AND ({app_version:String} = '' OR app_version = {app_version:String})
              AND ({content_id:Int64}   = 0  OR content_id  = {content_id:Int64})
            GROUP BY
                video_session_id, playback_instance_no, user_id, content_id, platform, country,
                app_version, video_type, transition_at, from_state, to_state, trigger_event_type,
                trigger_event, seconds_in_previous_state, transition_sequence
            HAVING net > 0
        )
        GROUP BY from_state, to_state
        HAVING transitions > 0
    )
-- FULL OUTER JOIN, so a key present on only one side is caught rather than dropped. An INNER JOIN
-- here would compare the intersection and report zero differences while one side was missing an
-- entire edge, which is the classic way a diff query passes without checking anything.
SELECT
    ifNull(nullIf(o.from_state, ''), r.from_state) AS from_state,
    ifNull(nullIf(o.to_state, ''), r.to_state)     AS to_state,
    multiIf(
        o.transitions = 0 AND r.transitions > 0, 'missing from optimized',
        r.transitions = 0 AND o.transitions > 0, 'unexpected in optimized',
                                                 'value mismatch') AS side,
    o.transitions AS opt_transitions, r.transitions AS ref_transitions,
    o.sessions    AS opt_sessions,    r.sessions    AS ref_sessions,
    o.avg_seconds AS opt_avg_seconds, r.avg_seconds AS ref_avg_seconds,
    o.max_seconds AS opt_max_seconds, r.max_seconds AS ref_max_seconds,
    o.entered_by_timeout AS opt_timeouts, r.entered_by_timeout AS ref_timeouts
FROM optimized AS o
FULL OUTER JOIN reference AS r
    ON o.from_state = r.from_state AND o.to_state = r.to_state
WHERE o.transitions != r.transitions
   OR o.sessions    != r.sessions
   OR o.max_seconds != r.max_seconds
   OR o.entered_by_timeout != r.entered_by_timeout
   OR abs(o.avg_seconds - r.avg_seconds) > 0.05
ORDER BY from_state, to_state
SETTINGS max_execution_time = 120,
         timeout_before_checking_execution_speed = 0;
