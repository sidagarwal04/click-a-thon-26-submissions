-- b05 — per-hour peak + time-weighted average for one day, no filter.
-- Statement shape: "peak and average concurrency at ... hour ... grain".
-- Serving path: stored rows of cc_hour_agg at the headline cube level — the hour
-- IS the storage grain, so peak/peak_minute/integral are read, not computed.
SELECT
    hour,
    peak,
    peak_minute,
    integral,
    round(avg_concurrent, 2) AS avg_concurrent
FROM v_concurrency_hour_total
WHERE hour >= {p_day:DateTime}
  AND hour <  {p_day:DateTime} + INTERVAL 1 DAY
ORDER BY hour
