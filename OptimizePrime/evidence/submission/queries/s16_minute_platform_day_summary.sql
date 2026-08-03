-- s16 · MINUTE grain · platform filter (ANDROID_PHONE) · whole day.
-- Dimension pinned on the leading column of cc_minute_delta's sort key.
WITH series AS
(
    SELECT minute,
           toInt64(sum(d) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM
    (
        SELECT minute, sum(delta) AS d
        FROM cc_minute_delta
        WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00' AND platform = 'ANDROID_PHONE'
        GROUP BY minute
        ORDER BY minute WITH FILL FROM toDateTime('2026-07-31 00:00:00') TO toDateTime('2026-08-01 00:00:00') STEP toIntervalSecond(60)
    )
)
SELECT 'ANDROID_PHONE' AS platform,
       count() AS minute_buckets,
       max(concurrent) AS peak,
       argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
       round(avg(concurrent), 4) AS avg_concurrent,
       sum(concurrent) * 60 AS integral
FROM series
FORMAT TSVWithNames
