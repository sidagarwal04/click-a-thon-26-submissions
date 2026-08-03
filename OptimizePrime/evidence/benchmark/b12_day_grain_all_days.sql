-- b12 — per-day peak + time-weighted average, every day in the file, no filter.
-- Statement shape: "peak and average concurrency at ... day grain".
-- Serving path: v_concurrency_day_total — max over each day's 24 stored hour rows
-- (legal over TIME only because hour-clipping makes each hour's max absolute).
-- avg divides by a full 86,400 s; active_hours exposes partial first/last days.
SELECT
    day,
    peak,
    peak_minute,
    integral,
    round(avg_concurrent, 2) AS avg_concurrent,
    active_hours
FROM v_concurrency_day_total
ORDER BY day
