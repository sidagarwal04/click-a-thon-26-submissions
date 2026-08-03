-- UNKNOWN_VOCABULARY: every event_type and event value the classifier does not recognise.
--
--   ./scripts/vocabulary_check.sh [database]
--
-- Run this FIRST on any new data, before deriving anything. It answers in seconds whether a
-- human decision is needed, which is the difference between finding out now and finding out
-- from a wrong number at hour 22.
--
-- The data dictionary calls its list "current event types". That is an admission the list is
-- not exhaustive, and the live stream has already proved it by introducing two `event` values
-- that appear nowhere in the validated corpus.
--
-- WHAT AN UNKNOWN VALUE DOES TODAY, which is why this is a report and not an alarm: it is
-- NEUTRAL. It carries the previous state forward and can never, by itself, start counting
-- someone as watching. An unknown value that defaulted to active would manufacture viewing
-- time, which is the exact failure this problem exists to prevent; an unknown value that
-- defaults to neutral can at worst fail to extend it. Those two errors are not symmetric, so
-- the conservative default is the correct one and an unknown value is safe by construction.
--
-- The classifier vocabulary is duplicated here as literals rather than read from
-- 03_event_state.sql. That is deliberate: 03_event_state.sql is validated against a
-- brute-force oracle at zero diffs, and refactoring it to read vocabulary from a table to
-- avoid duplicating two arrays would put a validated file at risk to save nine lines. If the
-- classifier changes, change both, and the parity gate will catch it if you do not.
WITH
    ['VideoSessionStart', 'VideoPlay', 'VideoHeartbeat', 'AppBackgrounded',
     'AppForegrounded', 'VideoSessionEnd', 'VideoError']                      AS known_event_types,
    -- Values that DECIDE state when they arrive on a VideoHeartbeat. Everything else on a
    -- heartbeat is neutral telemetry by design, so it is not listed and not reported.
    ['pause', 'speed-pause', 'AdPause',
     'resume', 'speed-resume', 'AdResume']                                    AS decisive_heartbeat_events
SELECT * FROM
(
    -- An unknown event_type is the serious one: the whole state machine keys on event_type
    -- first, so a new type is invisible to every branch and lands as neutral.
    SELECT
        'UNKNOWN_EVENT_TYPE'                       AS finding,
        event_type                                 AS value,
        ''                                         AS context,
        count()                                    AS events,
        uniqExact(video_session_id)                AS sessions,
        min(event_timestamp)                       AS first_seen,
        max(event_timestamp)                       AS last_seen,
        'treated as NEUTRAL: carries previous state, never opens playback' AS effect
    FROM raw_events
    WHERE event_timestamp < {frozen_before:String}
      AND event_type NOT IN known_event_types
    GROUP BY event_type

    UNION ALL

    -- A new `event` value arriving on a heartbeat. Informational rather than alarming: it is
    -- neutral unless it is a pause/resume synonym, which is the one case a human must rule on.
    SELECT
        'UNKNOWN_HEARTBEAT_EVENT',
        event,
        'VideoHeartbeat',
        count(),
        uniqExact(video_session_id),
        min(event_timestamp),
        max(event_timestamp),
        'treated as NEUTRAL: decide only if it is a pause or resume synonym'
    FROM raw_events
    WHERE event_timestamp < {frozen_before:String}
      AND event_type = 'VideoHeartbeat'
      AND event NOT IN decisive_heartbeat_events
      -- Only report values that are NEW relative to the validated corpus. Reporting all 40-odd
      -- known-neutral telemetry values every run would bury the one line that matters.
      AND event NOT IN (
            SELECT DISTINCT event FROM raw_events
            WHERE event_type = 'VideoHeartbeat' AND event_timestamp < {baseline_before:String})
    GROUP BY event
)
ORDER BY finding, events DESC;
