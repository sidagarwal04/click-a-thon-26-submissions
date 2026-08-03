-- INSIGHTS PIPELINE: rebuild both user-journey tables for the users a batch touched.
--
--   Parameters: tolerance_s (unused here, accepted for a uniform call), from_ts, to_ts
--
-- ONE FILE, TWO INSERTS, because both tables are the same computation read two ways: consecutive
-- sessions of one user, ordered by when they became ACTIVE. Splitting them would mean deriving
-- that sequence twice, and the second copy is what would drift.
--
-- SCOPED TO TOUCHED USERS, not touched sessions, and the distinction is load-bearing. A transition
-- is a property of a PAIR of sessions, so a new session arriving makes a transition out of a
-- session that may be hours old and outside any window. Selecting by user and then re-deriving
-- that user's whole sequence is what makes the incremental result identical to a full rebuild.
--
-- IDEMPOTENT WITHOUT A GUARD: both targets are ReplacingMergeTree(version) keyed on the
-- transition's identity, and every run stamps a higher version, so a second run over the same
-- window supersedes rather than adds. Read with FINAL, or with argMax(version).
--
-- WHY session_insight_facts AND NOT raw_events: that table already carries first_active_at and
-- last_active_at derived from the validated foreground intervals, so a switch inherits the
-- foreground-only definition instead of re-implementing the state machine here.
INSERT INTO user_content_transitions
WITH
    -- 10 minutes. A gap longer than this is not a switch, it is two separate viewing occasions,
    -- and calling it a switch would attribute an evening's second session to whatever the viewer
    -- happened to watch at lunchtime.
    600 AS max_switch_gap_s,

    touched AS
    (
        SELECT DISTINCT user_id
        FROM raw_events
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
    ),

    -- Dedup to one row per session BEFORE sequencing. session_insight_facts is a
    -- ReplacingMergeTree, so a re-derived session has several stored versions until a merge
    -- collapses them, and sequencing over the raw table would interleave a session with itself.
    -- argMax(..., version) rather than FINAL, the pattern every insight query here uses: same
    -- answer, no full-range merge.
    --
    -- first_active_at = 0 is the sentinel for a session that never had a foreground interval.
    -- Excluded: a session nobody ever watched cannot be a point on a journey.
    sess AS
    (
        SELECT
            video_session_id                       AS sid,
            argMax(user_id, version)               AS s_user_id,
            argMax(content_id, version)            AS s_content_id,
            argMax(title, version)                 AS s_title,
            argMax(category, version)              AS s_category,
            argMax(video_type, version)            AS s_video_type,
            argMax(platform, version)              AS s_platform,
            argMax(first_active_at, version)       AS s_first_active_at,
            argMax(last_active_at, version)        AS s_last_active_at,
            argMax(session_end_at, version)        AS s_session_end_at,
            argMax(background_count, version)      AS s_background_count
        FROM session_insight_facts
        WHERE user_id IN (SELECT user_id FROM touched)
        GROUP BY video_session_id
        HAVING s_first_active_at > toDateTime(0)
    ),

    -- The sequence. lagInFrame with an explicit one-row frame rather than neighbor(), which is
    -- documented as unreliable across block boundaries. Two lags back, not one: identifying a
    -- RETURN to previous content needs the content before the previous one.
    seq AS
    (
        SELECT
            *,
            lagInFrame(sid)             OVER w AS prev_sid,
            lagInFrame(s_content_id)      OVER w AS prev_content_id,
            lagInFrame(s_title)           OVER w AS prev_title,
            lagInFrame(s_category)        OVER w AS prev_category,
            lagInFrame(s_video_type)      OVER w AS prev_video_type,
            lagInFrame(s_platform)        OVER w AS prev_platform,
            lagInFrame(s_last_active_at)  OVER w AS prev_last_active_at,
            lagInFrame(s_session_end_at)  OVER w AS prev_session_end_at,
            lagInFrame(s_background_count) OVER w AS prev_background_count,
            lagInFrame(s_content_id, 2)   OVER w AS prev2_content_id
        FROM sess
        WINDOW w AS (PARTITION BY s_user_id ORDER BY s_first_active_at ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    )
SELECT
    s_user_id        AS user_id,
    prev_content_id  AS from_content_id,
    prev_title       AS from_title,
    prev_category    AS from_category,
    prev_video_type  AS from_video_type,
    s_content_id     AS to_content_id,
    s_title          AS to_title,
    s_category       AS to_category,
    s_video_type     AS to_video_type,
    prev_sid         AS from_session_id,
    sid              AS to_session_id,
    s_first_active_at AS transition_at,
    toInt32(dateDiff('second', prev_last_active_at, s_first_active_at)) AS gap_seconds,
    -- Overlap of the two active spans. greatest(0, ...) because a clean switch has none, and a
    -- negative overlap is not a concept.
    toInt32(greatest(0, dateDiff('second', s_first_active_at, least(prev_last_active_at, s_last_active_at)))) AS overlap_seconds,
    prev_platform    AS from_platform,
    s_platform       AS to_platform,
    -- ORDER MATTERS HERE. parallel_multi_device is tested FIRST, before any gap-based rule, because
    -- overlapping sessions also have a small or negative gap and would otherwise be classified as
    -- a fast switch. That misclassification is exactly what the plan's checklist forbids.
    multiIf(
        overlap_seconds > 0,                                 'parallel_multi_device',
        prev2_content_id = s_content_id,                       'return_to_previous_content',
        prev_session_end_at > toDateTime64(0, 3),            'switch_after_end',
        prev_background_count > 0,                           'switch_after_background',
                                                             'direct_switch') AS transition_type,
    toUInt64(toUnixTimestamp64Milli(now64(3))) AS version,
    now() AS updated_at
FROM seq
WHERE prev_sid != ''
  AND prev_content_id != s_content_id
  -- Overlapping pairs are kept regardless of gap: they are the parallel-device answer and dropping
  -- them would leave the switch counts looking cleaner than the truth.
  AND (gap_seconds <= toInt32(max_switch_gap_s) OR overlap_seconds > 0);


INSERT INTO user_platform_transitions
WITH
    -- 5 minutes, tighter than the content-switch window. Picking up the same match on another
    -- device is a deliberate act that happens quickly; half an hour later is a new sitting.
    300 AS max_handoff_gap_s,

    touched AS
    (
        SELECT DISTINCT user_id
        FROM raw_events
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
    ),
    sess AS
    (
        SELECT
            video_session_id                 AS sid,
            argMax(user_id, version)         AS s_user_id,
            argMax(content_id, version)      AS s_content_id,
            argMax(title, version)           AS s_title,
            argMax(platform, version)        AS s_platform,
            argMax(first_active_at, version) AS s_first_active_at,
            argMax(last_active_at, version)  AS s_last_active_at
        FROM session_insight_facts
        WHERE user_id IN (SELECT user_id FROM touched)
        GROUP BY video_session_id
        HAVING s_first_active_at > toDateTime(0)
    ),
    -- PARTITIONED BY (user, content), not by user alone. A handoff is the same content moving
    -- device, so the previous session that matters is the previous session OF THAT CONTENT.
    -- Partitioning by user alone would compare a TV match against a phone comedy watched in
    -- between and call it a device change.
    seq AS
    (
        SELECT
            *,
            lagInFrame(sid)            OVER w AS prev_sid,
            lagInFrame(s_platform)       OVER w AS prev_platform,
            lagInFrame(s_last_active_at) OVER w AS prev_last_active_at,
            lagInFrame(s_platform, 2)    OVER w AS prev2_platform
        FROM sess
        WINDOW w AS (PARTITION BY s_user_id, s_content_id ORDER BY s_first_active_at ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    )
SELECT
    s_user_id       AS user_id,
    s_content_id    AS content_id,
    s_title         AS title,
    prev_platform   AS from_platform,
    s_platform      AS to_platform,
    prev_sid        AS from_session_id,
    sid             AS to_session_id,
    s_first_active_at AS transition_at,
    toInt32(dateDiff('second', prev_last_active_at, s_first_active_at)) AS gap_seconds,
    toInt32(greatest(0, dateDiff('second', s_first_active_at, least(prev_last_active_at, s_last_active_at)))) AS overlap_seconds,
    multiIf(
        overlap_seconds > 0,                          'parallel_multi_device',
        prev2_platform = s_platform,                    'return_to_previous_device',
        gap_seconds <= toInt32(max_handoff_gap_s),    'handoff',
                                                      'unknown') AS transition_type,
    toUInt64(toUnixTimestamp64Milli(now64(3))) AS version,
    now() AS updated_at
FROM seq
WHERE prev_sid != ''
  AND prev_platform != s_platform;
