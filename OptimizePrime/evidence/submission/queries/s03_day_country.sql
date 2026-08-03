-- s03 · DAY grain · country filter · session tier (cube_level = 2)
SELECT country,
       max(cc_hour_agg.peak) AS peak,
       argMax(cc_hour_agg.peak_minute,
              (cc_hour_agg.peak, -toInt64(toUInt32(cc_hour_agg.peak_minute)))) AS peak_minute,
       sum(cc_hour_agg.integral) AS integral,
       round(sum(cc_hour_agg.integral) / 86400, 4) AS avg_concurrent
FROM cc_hour_agg FINAL
WHERE cube_level = 2 AND platform = '*' AND content_id = -1
  AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
  AND (cc_hour_agg.peak != 0 OR cc_hour_agg.integral != 0)
GROUP BY country
ORDER BY peak DESC, country ASC
FORMAT TSVWithNames
