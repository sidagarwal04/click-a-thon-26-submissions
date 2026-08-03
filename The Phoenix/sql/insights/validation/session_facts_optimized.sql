-- OPTIMIZED side of the session_insight_facts validation pair.
--
-- Reads the serving table and nothing else. Emits exactly the columns of
-- session_facts_ground_truth.sql, in exactly that order, so the two can be diffed line by line.
-- A reordering here is a diff on every row.
--
-- FINAL, because session_insight_facts is a ReplacingMergeTree and an unmerged part may still
-- hold a superseded version of a re-derived session. FINAL is the correct read for a
-- correctness comparison and the wrong read for a dashboard, which is why the benchmark queries
-- aggregate with argMax(version) instead.
--
-- RESTRICTED TO THE FROZEN SLICE BY SESSION, NOT BY ROW. The ground truth runs over the raw CSV,
-- which is exactly the 905,558-row frozen corpus. The serving table also holds live sessions.
-- A row filter would compare a session the CSV knows in full against a session the service knows
-- in full plus more, and every such session would diff for a reason that is not a defect. So the
-- filter is `last_event_at < frozen_before`: a session is comparable only if ALL of its events
-- fall inside the corpus.
SELECT
    video_session_id,
    user_id,
    content_id,
    title,
    category,
    video_type,
    platform,
    country,
    app_version,
    toString(session_start)   AS session_start,
    toString(first_play_at)   AS first_play_at,
    toString(session_end_at)  AS session_end_at,
    toString(first_active_at) AS first_active_at,
    toString(last_active_at)  AS last_active_at,
    active_seconds,
    active_interval_count,
    background_count,
    foreground_return_count,
    pause_count,
    resume_count,
    heartbeat_count,
    video_error_count,
    reached_first_heartbeat,
    active_after_1m,
    active_after_5m,
    active_after_10m,
    active_after_15m,
    ended_normally,
    abandoned,
    timed_out,
    reopened_after_end
FROM session_insight_facts FINAL
WHERE last_event_at < {frozen_before:String}
ORDER BY video_session_id;
