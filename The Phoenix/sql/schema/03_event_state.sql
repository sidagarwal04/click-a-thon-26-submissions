-- The state machine, in one place.
--
-- Every consumer (batch derivation, incremental derivation) reads this view, so the
-- classification cannot drift between them. The oracle keeps its own independent copy on
-- purpose: a specification that imports the implementation validates nothing.
--
-- Three buckets, and the third is the one that matters:
--
--   DEACTIVATING  AppBackgrounded, VideoSessionEnd, VideoError, and the pause family
--   REACTIVATING  VideoSessionStart, VideoPlay, AppForegrounded, and the resume family
--   NEUTRAL       the other 34 VideoHeartbeat values: telemetry that proves the client is
--                 alive but says nothing about whether playback is in the foreground
--
-- Neutral events must NOT flip state. Treating them as reactivating (which a
-- "default to open" classification does) means a `pause` is cancelled by the very next
-- buffer-health or network-activity row, so paused time is counted as watching. Longer
-- pauses carry more telemetry, so the error grows with the thing being excluded.
--
-- An unrecognised event value is neutral, not open. New event types are promised by the
-- data dictionary, and an unknown event should never be able to manufacture viewing time.
CREATE OR REPLACE VIEW event_state AS
WITH
    collapsed AS
    (
        -- One row per (session, millisecond). Ties are collapsed with min(), which both
        -- skips NULLs (so a decisive event beats simultaneous telemetry) and lets a close
        -- beat an open at the same instant.
        --
        -- Millisecond, not second: 29% of events share a second with another, and
        -- collapsing at second precision reads a pause and its resume in the same second as
        -- "paused". Keeping milliseconds drops ambiguous pause/resume pairs from 2,887 to
        -- 381. The remaining 381 are genuinely simultaneous and the close wins, which errs
        -- toward not counting time we cannot prove was watched.
        SELECT
            video_session_id,
            ts,
            min(strict) AS strict_cls,
            min(loose)  AS loose_cls
        FROM
        (
            SELECT
                video_session_id,
                event_timestamp AS ts,
                -- strict: the pause family is deactivating
                multiIf(
                    event_type IN ('AppBackgrounded', 'VideoSessionEnd', 'VideoError'), 0,
                    event_type = 'VideoHeartbeat' AND event IN ('pause', 'speed-pause', 'AdPause'), 0,
                    event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded'), 1,
                    event_type = 'VideoHeartbeat' AND event IN ('resume', 'speed-resume', 'AdResume'), 1,
                    NULL) AS strict,
                -- loose: identical, except the pause family is neutral. Lets the pause
                -- ruling be re-measured on any dataset without touching this file.
                multiIf(
                    event_type IN ('AppBackgrounded', 'VideoSessionEnd', 'VideoError'), 0,
                    event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded'), 1,
                    event_type = 'VideoHeartbeat' AND event IN ('resume', 'speed-resume', 'AdResume'), 1,
                    NULL) AS loose
            FROM raw_events
        )
        GROUP BY video_session_id, ts
    )
SELECT
    video_session_id,
    ts,
    -- Carry the last decisive state forward across neutral rows. argMax over a window with
    -- epoch-0 standing in for "not decisive" picks the most recent decisive classification;
    -- if a session opens with telemetry and no start event, there is none, and the session
    -- is treated as open, matching the ruling that a missing start is a lost event rather
    -- than a lost viewer.
    coalesce(argMax(strict_cls, if(strict_cls IS NULL, toDateTime64(0, 3), ts)) OVER w, 1) AS is_open,
    coalesce(argMax(loose_cls,  if(loose_cls  IS NULL, toDateTime64(0, 3), ts)) OVER w, 1) AS is_open_pause_active
FROM collapsed
WINDOW w AS (PARTITION BY video_session_id ORDER BY ts ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);
