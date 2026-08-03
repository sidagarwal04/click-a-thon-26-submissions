-- =============================================================================
-- 010_recompute_sessions.sql — event-time state machine, one row per session
--
-- Deliberately NOT in ingest/sql/: everything there is idempotent DDL applied in
-- filename order by `sonyliv-ingest schema`. This is a parameterized INSERT that
-- the concurrency pipeline runs against a chosen workset, so it must not be swept
-- up by the schema applier.
--
-- Reads events_dedup, which means three things this logic would otherwise have to
-- do are already done:
--
--   * duplicate resolution — the view resolves the semantic event key by argMax
--     over row_version, deterministically, without FINAL and without waiting on a
--     merge;
--   * event classification — 003 stamped `signal` at insert time, so this
--     branches on a closed Enum8 rather than re-deriving 47 inconsistently-cased
--     event names. That classification would otherwise be duplicated in every
--     query that needs it, which is a drift risk;
--   * conflict tie-breaking — resolved_row_version already carries the documented
--     last-write-wins order.
--
-- What remains, and cannot be removed: the GROUP BY on (session_key, event_ts).
-- events_dedup returns one row per (session, ts, event_type, event), so a single
-- millisecond can still hold several rows — a background and a pause together, or
-- the periodic trio at one identical timestamp. Collapsing the instant and
-- applying stop-wins precedence is still required.
--
-- Parameters (textual {{db}}; the rest are server-side bound):
--   {session_keys:Array(UInt64)}  -- workset; EMPTY ARRAY means "every session"
--   {heartbeat_timeout_ms:UInt64}
--   {evaluation_as_of:String}     -- the ingest watermark, never a literal date
--   {policy_version:String}
--   {version:UInt64}              -- ms since epoch; higher wins on replacement
-- =============================================================================

INSERT INTO {{db}}.session_intervals
(
    session_start_date, session_key, video_session_id, version, policy_version,
    user_key, canonical_user_id, content_id, platform, country, app_version,
    video_type, has_terminal_end, terminal_end_time, intervals,
    source_event_count, computed_at
)
WITH
    {heartbeat_timeout_ms:UInt64} AS heartbeat_timeout_ms,
    toDateTime64({evaluation_as_of:String}, 3, 'UTC') AS evaluation_as_of,

    scoped_events AS
    (
        SELECT
            session_key, event_ts, signal, resolved_row_version,
            video_session_id, user_key, user_id, content_id,
            platform, app_version, country,
            -- policy signal_events = VideoPlay, or any VideoHeartbeat whose event
            -- is not 'pause'. On the signal enum that is exactly these three:
            -- 'liveness' covers every other heartbeat, including AdPause and
            -- speed-pause, which 003 deliberately classes here rather than as
            -- play-state transitions. 'error' is excluded (VideoError is not a
            -- heartbeat); 'pause' is excluded by the policy.
            signal IN ('play', 'resume', 'liveness') AS is_liveness
        FROM {{db}}.events_dedup
        WHERE event_ts <= evaluation_as_of
          AND (empty({session_keys:Array(UInt64)}) OR session_key IN {session_keys:Array(UInt64)})
    ),

    session_anchors AS
    (
        SELECT
            session_key,
            minIf(event_ts, signal = 'session_start') AS lifecycle_start_time,
            -- policy end_choice: first. min, not max.
            minIf(event_ts, signal = 'session_end')   AS terminal_end_time,
            countIf(signal = 'session_end') > 0       AS has_terminal_end,
            count()                                   AS source_event_count,

            -- session_static_anchor: VideoSessionStart, tie-broken on
            -- resolved_row_version so duplicate Starts sharing a timestamp
            -- resolve identically on every machine and every rerun.
            argMinIf(video_session_id, tuple(event_ts, resolved_row_version), signal = 'session_start') AS video_session_id,
            argMinIf(user_key,         tuple(event_ts, resolved_row_version), signal = 'session_start') AS user_key,
            argMinIf(user_id,          tuple(event_ts, resolved_row_version), signal = 'session_start') AS canonical_user_id,
            argMinIf(content_id,       tuple(event_ts, resolved_row_version), signal = 'session_start') AS content_id,
            argMinIf(platform,         tuple(event_ts, resolved_row_version), signal = 'session_start') AS platform,
            argMinIf(app_version,      tuple(event_ts, resolved_row_version), signal = 'session_start') AS app_version,
            argMinIf(country,          tuple(event_ts, resolved_row_version), signal = 'session_start') AS country
        FROM scoped_events
        GROUP BY session_key
        -- missing_start_action: quarantine. A session with no Start emits no row,
        -- so any row previously written for it survives untouched rather than
        -- being silently emptied.
        HAVING countIf(signal = 'session_start') > 0
    ),

    events_through_first_end AS
    (
        SELECT e.session_key AS session_key, e.event_ts AS event_ts,
               e.signal AS signal, e.is_liveness AS is_liveness
        FROM scoped_events AS e
        INNER JOIN session_anchors AS a USING (session_key)
        WHERE e.event_ts >= a.lifecycle_start_time
          AND (NOT a.has_terminal_end OR e.event_ts <= a.terminal_end_time)
    ),

    same_timestamp_assignments AS
    (
        -- No source sequence exists inside a millisecond; collapse the instant.
        SELECT
            session_key, event_ts,
            max(signal = 'session_start')     AS has_start,
            max(signal = 'session_end')       AS has_end,
            max(signal = 'background')        AS has_background,
            max(signal = 'foreground')        AS has_foreground,
            max(signal IN ('pause', 'error')) AS has_play_stop,
            max(signal IN ('play', 'resume')) AS has_play_start,
            max(is_liveness)                  AS has_liveness_signal
        FROM events_through_first_end
        GROUP BY session_key, event_ts
    ),

    setters AS
    (
        -- Stop-wins precedence, which is what makes an atomic same-millisecond
        -- pair resolve deterministically. Note this is precisely why 003 must NOT
        -- class speed-pause/speed-resume as pause/resume: 365 of 380 such pairs
        -- share a millisecond, so stop-wins would strand the session as stopped
        -- with no resume left to reopen it — measured at up to 41.9h of active
        -- time across 174 sessions, 106 of which never recovered.
        SELECT
            *,
            multiIf(has_end OR has_background, toInt8(-1), has_start OR has_foreground, toInt8(1), toInt8(0)) AS foreground_setter,
            multiIf(has_end OR has_play_stop,  toInt8(-1), has_play_start,              toInt8(1), toInt8(0)) AS playing_setter
        FROM same_timestamp_assignments
    ),

    state_after_assignment AS
    (
        -- foreground and playing are INDEPENDENT booleans, not one state.
        -- Measured: collapsing them disagrees at 38,958 of 905,558 event
        -- positions across 98.8% of sessions, and every disagreement is an
        -- overcount — a pause arriving while already backgrounded is swallowed,
        -- then the next foreground reopens a session whose player is paused.
        SELECT
            *,
            max(has_start) OVER state_window AS lifecycle_started,
            max(has_end)   OVER state_window AS terminal_end_seen,
            argMaxIf(foreground_setter, event_ts, foreground_setter != 0) OVER state_window AS foreground_state,
            argMaxIf(playing_setter,    event_ts, playing_setter    != 0) OVER state_window AS playing_state
        FROM setters
        WINDOW state_window AS
        (
            PARTITION BY session_key ORDER BY event_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    ),

    eligible_signals AS
    (
        -- renew_only_when: {started, not ended, foreground, playing}. No lease
        -- term, so eligibility is lease-independent and there is no fixed point.
        SELECT
            *,
            has_liveness_signal
                AND lifecycle_started = 1
                AND terminal_end_seen = 0
                AND foreground_state = 1
                AND playing_state = 1 AS is_eligible_signal
        FROM state_after_assignment
    ),

    leased_state AS
    (
        SELECT
            *,
            maxIf(event_ts, is_eligible_signal) OVER state_window AS last_eligible_signal,
            leadInFrame(event_ts, 1, evaluation_as_of + toIntervalMillisecond(heartbeat_timeout_ms))
                OVER full_window AS next_event_time
        FROM eligible_signals
        WINDOW
            state_window AS (PARTITION BY session_key ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
            full_window  AS (PARTITION BY session_key ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
    ),

    candidate_segments AS
    (
        SELECT
            session_key,
            event_ts AS start_time,
            least(next_event_time, last_eligible_signal + toIntervalMillisecond(heartbeat_timeout_ms)) AS end_time
        FROM leased_state
        WHERE lifecycle_started = 1
          AND terminal_end_seen = 0
          AND foreground_state = 1
          AND playing_state = 1
          AND last_eligible_signal > toDateTime64(0, 3, 'UTC')
          AND event_ts < last_eligible_signal + toIntervalMillisecond(heartbeat_timeout_ms)
    ),

    -- Segments provably cannot overlap: end_i = least(next_event_time_i, ...) is
    -- at most t_{i+1}, and any later surviving row starts at t_j >= t_{i+1}. So
    -- "max of all previous ends" always equals the immediately previous end, and
    -- a lag replaces the running-max window this used to carry.
    marked_islands AS
    (
        SELECT
            *,
            start_time > lagInFrame(end_time, 1, toDateTime64(0, 3, 'UTC')) OVER
            (
                PARTITION BY session_key ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS starts_new_island
        FROM candidate_segments
        WHERE end_time > start_time
    ),

    numbered_islands AS
    (
        SELECT
            *,
            sum(starts_new_island) OVER
            (
                PARTITION BY session_key ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS island_number
        FROM marked_islands
    ),

    per_session AS
    (
        SELECT
            session_key,
            arraySort(x -> x.1, groupArray(tuple(island_start, island_end))) AS intervals
        FROM
        (
            SELECT session_key, island_number,
                   min(start_time) AS island_start,
                   max(end_time)   AS island_end
            FROM numbered_islands
            GROUP BY session_key, island_number
        )
        GROUP BY session_key
    )

SELECT
    toDate(a.lifecycle_start_time) AS session_start_date,
    a.session_key,
    a.video_session_id,
    {version:UInt64}        AS version,
    {policy_version:String} AS policy_version,
    a.user_key,
    a.canonical_user_id,
    a.content_id,
    a.platform,
    a.country,
    a.app_version,
    -- content_dict is COMPLEX_KEY_HASHED, so the key must be a tuple even though
    -- it is a single Int64. Its declared default is 'unknown', matching
    -- content_dim's own DEFAULT, so a catalogue miss and a blank video_type land
    -- in the same bucket rather than splitting a GROUP BY.
    dictGetOrDefault({{db}}.content_dict, 'video_type', tuple(a.content_id), 'unknown') AS video_type,
    a.has_terminal_end,
    a.terminal_end_time,
    -- join_use_nulls = 0 yields an empty array for a session with no active time.
    -- That empty array IS the retraction: the day rebuild reads it and the
    -- session's former contribution disappears with nothing deleted.
    p.intervals,
    a.source_event_count,
    now64(3) AS computed_at
FROM session_anchors AS a
LEFT JOIN per_session AS p USING (session_key)
SETTINGS join_use_nulls = 0;
