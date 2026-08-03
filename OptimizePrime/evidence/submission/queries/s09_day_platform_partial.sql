-- s09 · DAY grain · PARTIAL platform filter (platform IN two values) · session tier.
-- THE SHAPE THE CUBE DOES NOT SERVE. max(peak_A, peak_B) is NOT peak(A u B) --
-- they peak at different minutes. The union peak must be recomputed at minute grain.
-- This query returns the TRUE union peak next to the two wrong shortcuts, so the
-- size of the error is visible rather than asserted.
WITH change_points AS
(
    SELECT toStartOfHour(minute) AS hour, minute, sum(delta) AS dd
    FROM cc_minute_delta
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      AND platform IN ('ANDROID_PHONE', 'JIO_ANDROID_TV')
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
),
shortcut AS
(
    SELECT max(peak) AS max_of_cube_peaks, sum(peak) AS sum_of_cube_peaks
    FROM
    (
        SELECT platform, max(peak) AS peak
        FROM cc_hour_agg FINAL
        WHERE cube_level = 1 AND country = '*' AND content_id = -1
          AND platform IN ('ANDROID_PHONE', 'JIO_ANDROID_TV')
          AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
        GROUP BY platform
    )
)
SELECT ['ANDROID_PHONE', 'JIO_ANDROID_TV'] AS platforms,
       max(concurrent) AS peak_true_union,
       argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent * hold_s) AS integral,
       round(sum(concurrent * hold_s) / 86400, 4) AS avg_concurrent,
       any(shortcut.max_of_cube_peaks) AS wrong_max_of_peaks,
       any(shortcut.sum_of_cube_peaks) AS wrong_sum_of_peaks,
       count() AS change_points_scanned
FROM curve CROSS JOIN shortcut
FORMAT TSVWithNames
