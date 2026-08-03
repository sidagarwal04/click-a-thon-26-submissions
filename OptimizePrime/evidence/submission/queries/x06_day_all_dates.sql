-- x06 · DAY grain across EVERY output date the pipeline produced (not just the
-- headline day). 2026-07-31 is the day the file is about; the rest are the tail of
-- long-running / mis-stamped sessions the model still has to place somewhere.
SELECT day, peak, peak_minute, integral, round(avg_concurrent, 4) AS avg_concurrent, active_hours
FROM v_concurrency_day_total
ORDER BY peak DESC, day ASC
LIMIT 15
FORMAT TSVWithNames
