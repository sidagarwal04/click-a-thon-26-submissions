-- s12 · HOUR grain · platform filter (ANDROID_PHONE) · session tier.
-- Sort-key prefix equality read of cc_hour_agg at cube_level 1.
SELECT hour, peak, peak_minute, integral, round(integral / 3600, 4) AS avg_concurrent
FROM cc_hour_agg FINAL
WHERE platform = 'ANDROID_PHONE' AND country = '*' AND content_id = -1 AND cube_level = 1
  AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
  AND (peak != 0 OR integral != 0)
ORDER BY hour
FORMAT TSVWithNames
