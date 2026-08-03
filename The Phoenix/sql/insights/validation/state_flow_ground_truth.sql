-- GROUND TRUTH for state_flow.sql. Slow, obviously correct, and written to be read rather than to
-- be fast, per the plan document's Gate A: "create a slow, obviously correct reference query and
-- compare it with the optimized serving query".
--
--   frozen_before : String  (isolation, injected by ch.sh)
--
-- THE DIFFERENCE THAT MATTERS. The optimized query nets each (edge, session) pair in an inner
-- GROUP BY over three columns and aggregates the nets. This one does the thing that is impossible
-- to get wrong instead: it materialises the FULL identity of every transition, keeps only those
-- whose signs sum positive, and then counts rows. That is the definition of "which transitions
-- currently stand" written out literally, at the cost of grouping by fourteen columns.
--
-- If the two disagree, the optimized query is wrong, not this one.
--
-- This is the check that would have caught the first draft of state_flow.sql, which used
-- uniqExact(video_session_id) for the session count. uniqExact is not retraction-safe: a session
-- id appears on both an assertion and its retraction, and a distinct count has no way to cancel
-- them. It produced 3,405 transitions and 7,038 sessions on one edge, more sessions than
-- transitions, which is arithmetically impossible and is exactly the signature this file exists to
-- surface.
SELECT
    from_state,
    to_state,
    toInt64(count())                                  AS transitions,
    toInt64(uniqExact(video_session_id))              AS sessions,
    round(avg(seconds_in_previous_state), 1)          AS avg_seconds_in_from_state,
    toInt64(max(seconds_in_previous_state))           AS max_seconds_in_from_state,
    toInt64(countIf(trigger_event_type = 'HeartbeatTimeout')) AS entered_by_timeout
FROM
(
    -- Every column of the row, so two transitions that differ in any respect stay separate. A
    -- shorter GROUP BY here would collapse distinct transitions and quietly agree with a wrong
    -- optimized query, which is the one failure mode a reference implementation must not have.
    SELECT
        video_session_id,
        playback_instance_no,
        user_id,
        content_id,
        platform,
        country,
        app_version,
        video_type,
        transition_at,
        from_state,
        to_state,
        trigger_event_type,
        trigger_event,
        seconds_in_previous_state,
        transition_sequence,
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
    -- A transition that stands has net > 0. One that was retracted nets to zero and is gone.
    -- net > 1 would mean the same transition asserted twice, which the pipeline's atomic
    -- retract-and-assert is designed to make impossible; the diff will show it if it ever happens.
    HAVING net > 0
)
GROUP BY from_state, to_state
HAVING transitions > 0
ORDER BY transitions DESC
-- NO READ BUDGET, and that is deliberate rather than an omission. This query is not served to
-- anyone: it exists to be run by hand against the optimized one. Capping it would mean tuning the
-- reference to fit the thing it is supposed to check.
SETTINGS max_execution_time = 120,
         timeout_before_checking_execution_speed = 0;
