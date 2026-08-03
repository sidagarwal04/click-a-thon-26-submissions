-- s08 · DAY grain · video_resolution filter (NEW column on the unseen day) · session tier.
-- video_resolution is an EVENT-level dimension, not a key of cc_minute_delta and not
-- derivable from content_dim, so it is served by the generic exact-filter fallback
-- v_session_minutes (session_intervals expanded to minutes, joined to the catalog).
-- v_session_minutes is DENSE per active minute, so integral = sum(concurrent) * 60 exactly.
SELECT video_resolution,
       max(c) AS peak,
       argMax(minute, (c, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(c) * 60 AS integral,
       round(sum(c) * 60 / 86400, 4) AS avg_concurrent
FROM
(
    SELECT video_resolution, minute, uniqExact(video_session_id) AS c
    FROM v_session_minutes
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
    GROUP BY video_resolution, minute
)
GROUP BY video_resolution
ORDER BY peak DESC, video_resolution ASC
LIMIT 10
FORMAT TSVWithNames
