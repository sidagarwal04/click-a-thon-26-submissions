-- raw_events -> foreground_intervals (batch path)
--
-- The state machine itself lives in the event_state view (sql/schema/event_state.sql), so
-- the batch and incremental paths cannot drift apart. This file is only about turning
-- classified events into intervals.
--
-- Parameters: tolerance_s, pause_inactive.
--
-- Needs per-session ordering, so it cannot be an insert-time MV: an MV sees one block and
-- would split sessions across insert boundaries, silently.
--
-- Dimensions come from the session's FIRST event and are held constant. 95 of 10,866
-- sessions report more than one platform and 120 more than one user_id, which is dirty data
-- rather than roaming. Holding them constant keeps session-to-dimension 1:1, without which
-- a session that drifts mid-minute would be counted twice at that minute.
INSERT INTO foreground_intervals
    (video_session_id, user_id, content_id, platform, country, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     video_type, interval_start, interval_end)
WITH
    {tolerance_s:UInt32} AS tol,
    dims AS
    (
        SELECT
            video_session_id,
            argMin(user_id, event_timestamp)     AS user_id,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version,
            -- The four dimensions the unseen day made filterable. Same first-event rule as
            -- platform and app_version above: a session reporting two audio languages or two
            -- resolutions is dirty data, not two sessions.
            argMin(audio_language, event_timestamp)    AS audio_language,
            argMin(subtitle_language, event_timestamp) AS subtitle_language,
            argMin(player_version, event_timestamp)    AS player_version,
            argMin(video_resolution, event_timestamp)  AS video_resolution
        FROM raw_events
        GROUP BY video_session_id
    ),
    -- A session that has ended cannot accrue foreground time. Without this cap, 385 intervals
    -- across 21 sessions ran past their session's last VideoSessionEnd, 336 of them by more
    -- than the gap tolerance, the worst by 2,171 seconds.
    --
    -- THE ROOT CAUSE IS NOT DUPLICATE END EVENTS. TASK.md attributes it to the 14 sessions
    -- carrying multiple VideoSessionEnd rows; measured, those sessions account for ZERO of the
    -- 385. What actually happens is that reactivating events arrive AFTER the last end
    -- (measured on the 21 sessions: 38 `resume`, 28 AppForegrounded, 13 VideoPlay), which flips
    -- is_open back to 1, and then the neutral telemetry that follows carries that reopened state
    -- forward under the argMax in event_state: 267 network-bandwidth rows, 88 Seek, and so on,
    -- each opening its own interval up to tol seconds long.
    --
    -- So the fix has to bound the session, not deduplicate its end events.
    ends AS
    (
        SELECT
            video_session_id,
            max(event_timestamp) AS last_end
        FROM raw_events
        WHERE event_type = 'VideoSessionEnd'
        GROUP BY video_session_id
    ),
    segments AS
    (
        SELECT
            video_session_id,
            ts,
            if({pause_inactive:UInt8}, is_open, is_open_pause_active) AS is_open,
            -- an event's state holds until the next event, capped by the gap tolerance:
            -- silence longer than the cap is not evidence of watching, whatever the last
            -- state said
            leadInFrame(ts) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            least(if(next_ts > ts, next_ts, ts + tol), ts + tol) AS seg_end
        FROM event_state
    )
SELECT
    s.video_session_id,
    d.user_id,
    d.content_id,
    d.platform,
    d.country,
    d.app_version,
    d.audio_language,
    d.subtitle_language,
    d.player_version,
    d.video_resolution,
    -- LEFT JOIN: an event whose content_id is missing from the catalogue still counts as
    -- watching. Losing it would understate concurrency, the one direction we cannot afford.
    c.video_type,
    toDateTime(s.ts)      AS interval_start,
    -- No interval may extend past the session's last end event. The epoch-0 comparison and not
    -- `IS NULL`: ClickHouse fills an unmatched LEFT JOIN with the column type's DEFAULT, not
    -- NULL, so `e.last_end IS NULL` is never true and `least(seg_end, e.last_end)` would clamp
    -- every interval in a session with no end event to 1970. All 10,866 sessions in this corpus
    -- carry an end, so an INNER JOIN would behave identically here and silently drop those
    -- sessions on a day that has any. Measured, so stated: the trap is real and this avoids it.
    toDateTime(if(e.last_end > toDateTime64(0, 3), least(s.seg_end, e.last_end), s.seg_end)) AS interval_end
FROM segments AS s
INNER JOIN dims AS d ON s.video_session_id = d.video_session_id
LEFT JOIN ends AS e ON s.video_session_id = e.video_session_id
LEFT JOIN content AS c ON d.content_id = c.content_id
WHERE s.is_open = 1
  -- An event at or after the last end opens nothing. Capping alone would leave a zero-length
  -- interval per post-end event, and zero-length intervals still claim their minute downstream.
  AND (e.last_end = toDateTime64(0, 3) OR s.ts < e.last_end);
