-- s10 · DAY grain · COMBINED filter (platform = one value AND video_type = one value).
-- Crosses the two dimension families: an event-level key of cc_minute_delta and a
-- content-catalog attribute. Minute-tier recompute; same curve arithmetic as s05.
WITH change_points AS
(
    SELECT toStartOfHour(d.minute) AS hour, d.minute AS minute, sum(d.delta) AS dd
    FROM cc_minute_delta AS d
    WHERE d.minute >= '2026-07-31 00:00:00' AND d.minute < '2026-08-01 00:00:00'
      AND d.platform = 'ANDROID_PHONE'
      AND d.content_id IN (SELECT content_id FROM content_dim FINAL WHERE video_type = 'vod')
    GROUP BY hour, minute
),
curve AS
(
    SELECT hour, minute,
           toInt64(sum(dd) OVER w_run) AS concurrent,
           leadInFrame(toUInt32(minute), 1, toUInt32(toUInt32(hour) + 3600)) OVER w_fwd
               - toUInt32(minute) AS hold_s
    FROM change_points
    WINDOW
        w_run AS (PARTITION BY hour ORDER BY minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
        w_fwd AS (PARTITION BY hour ORDER BY minute ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)
)
SELECT 'ANDROID_PHONE' AS platform, 'vod' AS video_type,
       max(concurrent) AS peak,
       argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent * hold_s) AS integral,
       round(sum(concurrent * hold_s) / 86400, 4) AS avg_concurrent,
       count() AS change_points_scanned
FROM curve
FORMAT TSVWithNames
