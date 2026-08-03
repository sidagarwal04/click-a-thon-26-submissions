-- s02 · DAY grain · platform filter · session tier
-- cube_level = 1 => platform is REAL, country/content collapsed to sentinels.
-- Each platform's curve was materialised separately, so every peak here is a
-- genuine max of a genuine curve. These peaks DO NOT SUM to the total peak.
SELECT platform,
       max(cc_hour_agg.peak) AS peak,
       argMax(cc_hour_agg.peak_minute,
              (cc_hour_agg.peak, -toInt64(toUInt32(cc_hour_agg.peak_minute)))) AS peak_minute,
       sum(cc_hour_agg.integral) AS integral,
       round(sum(cc_hour_agg.integral) / 86400, 4) AS avg_concurrent
FROM cc_hour_agg FINAL
WHERE cube_level = 1 AND country = '*' AND content_id = -1
  AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
  AND (cc_hour_agg.peak != 0 OR cc_hour_agg.integral != 0)
GROUP BY platform
ORDER BY peak DESC, platform ASC
FORMAT TSVWithNames
