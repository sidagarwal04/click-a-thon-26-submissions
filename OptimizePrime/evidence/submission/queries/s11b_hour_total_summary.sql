-- s11b · HOUR grain rolled to one row: the max hourly peak and the mean of the
-- 24 hourly time-weighted averages (hours with no rows are genuine zeros).
SELECT count() AS hours_with_rows,
       max(peak) AS peak_over_hours,
       argMax(peak_minute, (peak, -toInt64(toUInt32(peak_minute)))) AS peak_minute_of_day,
       argMax(hour, (peak, -toInt64(toUInt32(hour)))) AS peak_hour,
       sum(integral) AS integral_over_day,
       round(sum(integral) / 86400, 4) AS avg_concurrent_over_day,
       round(max(integral) / 3600, 4) AS busiest_hour_avg,
       argMax(hour, integral) AS busiest_hour_by_avg,
       round(min(integral) / 3600, 4) AS quietest_stored_hour_avg
FROM v_concurrency_hour_total
WHERE hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
FORMAT TSVWithNames
