-- s11 · HOUR grain · no filter · session tier. The hour IS the storage grain of
-- cc_hour_agg: peak / peak_minute / integral are READ, not computed.
-- avg_concurrent here is the hour's own time-weighted average (integral / 3600).
SELECT hour, peak, peak_minute, integral, round(avg_concurrent, 4) AS avg_concurrent
FROM v_concurrency_hour_total
WHERE hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
ORDER BY hour
FORMAT TSVWithNames
