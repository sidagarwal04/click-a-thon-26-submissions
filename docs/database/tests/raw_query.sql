WITH
 toDateTime64('2026-07-23 15:03:00', 3, 'UTC') AS report_start,
    toDateTime64('2026-07-23 15:04:00', 3, 'UTC') AS report_end,
    false AS use_heartbeat_timeout,
    90 AS heartbeat_timeout_seconds,
raw AS (
    SELECT
        video_session_id,
        event_timestamp,
        event,
        event_type,
        CASE
            WHEN event_type = 'VideoHeartbeat' AND event IN ('pause','AppBackgrounded','VideoSessionEnd','VideoError','speed-pause','AdPause') THEN 0
            WHEN event_type = 'VideoHeartbeat' AND event IN ('buffer-health','network-activity','video-resize','VideoSessionStart','resume','BufferEnd','BufferStart','video_forward','Play','Seek','AdSkipTrueView','downshift','network-bandwidth','upshift','AppForegrounded','video_rewind','dropped-frames','download_initiated','AdBufferStart','next_video_click','chromecast_clicked','AdBufferEnd','network-change','golive','go_live_click','speed-change','speed-resume','download_completed','download_asset_played','AdResume','chromecast_started','video_quality_change','preview_watched','audio-language','preroll-disabled','AdClick','subtitle-language','download_asset_play_stop','download_deleted','download_resumed','premium_button_click') THEN 1
            WHEN event_type = 'VideoSessionStart' THEN 1
            WHEN event_type = 'VideoSessionEnd' THEN 0
            WHEN event_type = 'VideoError' THEN 0
            WHEN event_type = 'AppForegrounded' THEN 1
            WHEN event_type = 'VideoPlay' THEN 1
            WHEN event_type = 'AppBackgrounded' THEN 0
            ELSE NULL
        END AS state_change
    FROM bronze.ott_events
    WHERE event_timestamp >= report_start - toIntervalSecond(if(use_heartbeat_timeout, heartbeat_timeout_seconds, 0))
      AND event_timestamp < report_end
),
win AS (
    SELECT
        *,
        maxIf(event_timestamp, state_change = 1) OVER w AS last_active_ts,
        maxIf(event_timestamp, state_change = 0) OVER w AS last_inactive_ts
    FROM raw
    WINDOW w AS (
        PARTITION BY video_session_id
        ORDER BY event_timestamp
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
),
flagged AS (
    SELECT
        *,
        if(
            state_change = 1
            AND (
                last_active_ts IS NULL
                OR last_inactive_ts > last_active_ts
                OR (
                    use_heartbeat_timeout
                    AND dateDiff('second', last_active_ts, event_timestamp) > heartbeat_timeout_seconds
                )
            ),
            1, 0
        ) AS seg_start
    FROM win
),
segmented AS (
    SELECT
        *,
        sum(seg_start) OVER (
            PARTITION BY video_session_id
            ORDER BY event_timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS seg_id
    FROM flagged
),
intervals AS (
    SELECT
        video_session_id,
        seg_id,
        minIf(event_timestamp, state_change = 1) AS active_start,
        least(
            ifNull(
                minIf(event_timestamp, state_change = 0),
                toDateTime64('2999-12-31 23:59:59.999', 3, 'UTC')
            ),
            if(
                use_heartbeat_timeout,
                maxIf(event_timestamp, state_change = 1) + toIntervalSecond(heartbeat_timeout_seconds),
                toDateTime64('2999-12-31 23:59:59.999', 3, 'UTC')
            )
        ) AS active_end
    FROM segmented
    GROUP BY video_session_id, seg_id
    HAVING countIf(state_change = 1) > 0
),
clipped_intervals AS (
    SELECT
        video_session_id,
        greatest(active_start, report_start) AS active_start,
        least(
            if(
                active_end = toDateTime64('1970-01-01 00:00:00.000', 3, 'UTC'),
                report_end,
                active_end
            ),
            report_end
        ) AS active_end
    FROM intervals
    WHERE active_start < report_end
      AND (
          active_end > report_start
          OR active_end = toDateTime64('1970-01-01 00:00:00.000', 3, 'UTC')
      )
) ,
interval_minutes AS (
    SELECT
        video_session_id,
        first_minute + toIntervalMinute(minute_offset) AS minute
    FROM (
        SELECT
            video_session_id,
            toStartOfMinute(active_start) AS first_minute,
            toStartOfMinute(active_end) AS last_minute,
            active_end
        FROM clipped_intervals
        WHERE active_end > active_start
    )
    ARRAY JOIN range(
        toUInt64(
            greatest(
                0,
                dateDiff(
                    'minute',
                    first_minute,
                    last_minute
                )
            )
        )
    ) AS minute_offset
    WHERE first_minute + toIntervalMinute(minute_offset) + toIntervalMinute(1) <= active_end
),
minute_counts AS (
    SELECT
        minute,
        uniqExact(video_session_id) AS fg_concurrency
    FROM interval_minutes
    GROUP BY minute
),

minutes AS (
    SELECT
        report_start + toIntervalMinute(number) AS minute
    FROM numbers(dateDiff('minute', report_start, report_end))
)

SELECT
    m.minute,
    ifNull(c.fg_concurrency, 0) AS fg_concurrency
FROM minutes AS m
LEFT JOIN minute_counts AS c ON c.minute = m.minute
ORDER BY m.minute;