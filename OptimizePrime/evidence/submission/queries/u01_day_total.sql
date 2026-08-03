-- u01 · DAY grain · no filter · USER tier.
-- User concurrency is a SET CARDINALITY per minute, not a running sum of deltas:
-- one user can hold several concurrent sessions, so +1/-1 deltas over-count.
-- cc_user_minute stores an AggregateFunction(uniqExact, String) state per
-- (dims, minute); collapsing dimensions means MERGING states, never summing counts.
WITH series AS
(
    SELECT minute, uniqExactMerge(active_state) AS concurrent_users
    FROM cc_user_minute FINAL
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
    GROUP BY minute
)
SELECT max(concurrent_users) AS peak_users,
       argMax(minute, (concurrent_users, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent_users) * 60 AS integral_user_seconds,
       round(sum(concurrent_users) * 60 / 86400, 4) AS avg_users,
       count() AS active_minute_buckets
FROM series
FORMAT TSVWithNames
