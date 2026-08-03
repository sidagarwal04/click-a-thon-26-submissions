-- u04 · DAY grain · platform filter · USER tier.
-- The same user watching on two platforms is counted in BOTH rows: these peaks
-- neither sum nor max to the total user peak. That is the definition, not a defect.
SELECT platform,
       max(concurrent_users) AS peak_users,
       argMax(minute, (concurrent_users, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent_users) * 60 AS integral_user_seconds,
       round(sum(concurrent_users) * 60 / 86400, 4) AS avg_users
FROM
(
    SELECT platform, minute, uniqExactMerge(active_state) AS concurrent_users
    FROM cc_user_minute FINAL
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
    GROUP BY platform, minute
)
GROUP BY platform
ORDER BY peak_users DESC, platform ASC
FORMAT TSVWithNames
