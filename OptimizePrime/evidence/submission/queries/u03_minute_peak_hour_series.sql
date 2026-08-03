-- u03 · MINUTE grain · no filter · USER tier, the peak hour, minute by minute.
SELECT minute, uniqExactMerge(active_state) AS concurrent_users
FROM cc_user_minute FINAL
WHERE minute >= '2026-07-31 11:00:00' AND minute < toDateTime('2026-07-31 11:00:00') + INTERVAL 1 HOUR
GROUP BY minute
ORDER BY minute
FORMAT TSVWithNames
