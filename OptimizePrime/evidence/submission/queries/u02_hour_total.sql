-- u02 · HOUR grain · no filter · USER tier. Peak users and time-weighted average
-- users per hour. Merge the states per minute FIRST, then max/sum over the hour.
SELECT toStartOfHour(minute) AS hour,
       max(concurrent_users) AS peak_users,
       argMax(minute, (concurrent_users, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent_users) * 60 AS integral_user_seconds,
       round(sum(concurrent_users) * 60 / 3600, 4) AS avg_users
FROM
(
    SELECT minute, uniqExactMerge(active_state) AS concurrent_users
    FROM cc_user_minute FINAL
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
    GROUP BY minute
)
GROUP BY hour
ORDER BY hour
FORMAT TSVWithNames
