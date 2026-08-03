-- ORACLE: brute-force foreground concurrency. Deliberately slow, obviously correct.
-- Everything the serving layer produces is validated against this, and only this.
-- Explodes every active segment into per-minute rows: exactly the approach the problem
-- statement rules out at scale. That is the point. It is the reference, not the product.
--
-- The classification is written out again here rather than reading the event_state view.
-- A specification that imports the implementation cannot catch the implementation's bugs.
--
-- Parameters:
--   tolerance_s      heartbeat gap that ends an interval when nothing else does
--   pause_inactive   1 = paused time is not watching, 0 = paused still counts
--
-- Three buckets:
--   DEACTIVATING  AppBackgrounded, VideoSessionEnd, VideoError, pause family
--   REACTIVATING  VideoSessionStart, VideoPlay, AppForegrounded, resume family
--   NEUTRAL       every other heartbeat value: carries the previous state forward, and
--                 must never flip it. Treating telemetry as reactivating cancels a pause
--                 at the next buffer-health row.
WITH
    {tolerance_s:UInt32} AS tol,
    {pause_inactive:UInt8} AS pause_off,
    collapsed AS
    (
        -- one row per (session, millisecond); min() skips NULLs, so a decisive event beats
        -- simultaneous telemetry, and a close beats an open at the same instant
        SELECT
            video_session_id,
            any(user_id)    AS user_id,
            any(content_id) AS content_id,
            any(platform)   AS platform,
            any(country)    AS country,
            ts,
            min(cls)        AS cls,
            -- Tracked separately from cls because cls conflates VideoSessionEnd with
            -- AppBackgrounded, VideoError and the pause family, and only a session END bounds
            -- the session. A backgrounded app can come back; an ended session cannot.
            max(is_end)     AS is_end
        FROM
        (
            SELECT
                video_session_id, user_id, content_id, platform, country,
                event_timestamp AS ts,
                event_type = 'VideoSessionEnd' AS is_end,
                multiIf(
                    event_type IN ('AppBackgrounded', 'VideoSessionEnd', 'VideoError'), 0,
                    pause_off AND event_type = 'VideoHeartbeat'
                        AND event IN ('pause', 'speed-pause', 'AdPause'), 0,
                    event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded'), 1,
                    event_type = 'VideoHeartbeat'
                        AND event IN ('resume', 'speed-resume', 'AdResume'), 1,
                    NULL) AS cls
            -- events_src: a view the runner defines. Locally it wraps file() and converts
            -- epoch millis; in the service it is raw_events. Same SQL either way.
            FROM events_src
        )
        GROUP BY video_session_id, ts
    ),
    stated AS
    (
        SELECT
            video_session_id, user_id, content_id, platform, country, ts,
            coalesce(argMax(cls, if(cls IS NULL, toDateTime64(0, 3), ts)) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 1) AS is_open,
            -- The session's LAST end, over the whole partition rather than a running frame: an
            -- interval is bounded by the final end, not by whichever end happened to precede it.
            -- Returns epoch 0 for a session with no end event, which segments below tests for.
            maxIf(ts, is_end) OVER (PARTITION BY video_session_id) AS last_end
        FROM collapsed
    ),
    segments AS
    (
        SELECT
            video_session_id, user_id, ts AS seg_start, is_open,
            -- 120 sessions report more than one user_id. The serving layer files a session
            -- under its first-seen user, so the oracle reports both readings and the gap
            -- between them stays a measured number rather than a definition.
            argMin(user_id, ts) OVER (PARTITION BY video_session_id) AS first_user,
            leadInFrame(ts) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            last_end,
            -- No segment may extend past the session's last VideoSessionEnd. A session that has
            -- ended cannot accrue foreground time, and 385 intervals in the batch path did.
            -- Derived independently here, on purpose: the oracle is the specification, so it
            -- must state the rule rather than import the pipeline's version of it. Parity is
            -- what then proves the two agree.
            least(
                least(if(next_ts > seg_start, next_ts, seg_start + tol), seg_start + tol),
                if(last_end > toDateTime64(0, 3), last_end, toDateTime64('2100-01-01 00:00:00', 3))
            ) AS seg_end
        FROM stated
    )
SELECT
    minute,
    uniqExact(video_session_id) AS concurrent_sessions,
    uniqExact(first_user)       AS concurrent_users,      -- gate: matches the serving layer
    uniqExact(user_id)          AS concurrent_users_raw   -- per-event attribution, for the divergence log
FROM
(
    SELECT
        video_session_id,
        user_id,
        first_user,
        -- half-open [seg_start, seg_end): dur-1 keeps a segment that lands exactly on a
        -- minute boundary from claiming the minute it never entered
        arrayJoin(timeSlots(toDateTime(seg_start),
                            toUInt32(greatest(dateDiff('second', seg_start, seg_end) - 1, 0)),
                            60)) AS minute
    FROM segments
    WHERE is_open = 1
      -- An event at or after the last end opens nothing at all. Capping alone would leave a
      -- zero-length segment per post-end event, and timeSlots still yields its minute.
      AND (last_end = toDateTime64(0, 3) OR seg_start < last_end)
)
GROUP BY minute
ORDER BY minute;
