-- s14 · MINUTE grain · no filter · session tier, whole day (1,440 minute buckets).
-- Densify recipe per docs/CONVENTIONS.md: WITH FILL on the DELTA inside the subquery
-- (a filled row defaults to delta 0), THEN the hour-partitioned running sum.
-- Filling the LEVEL with INTERPOLATE invents viewers across an hour boundary.
WITH series AS
(
    SELECT minute,
           toInt64(sum(d) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM
    (
        SELECT minute, sum(delta) AS d
        FROM cc_minute_delta
        WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
        GROUP BY minute
        ORDER BY minute WITH FILL FROM toDateTime('2026-07-31 00:00:00') TO toDateTime('2026-08-01 00:00:00') STEP toIntervalSecond(60)
    )
)
SELECT count() AS minute_buckets,
       max(concurrent) AS peak,
       argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
       round(avg(concurrent), 4) AS avg_concurrent,
       sum(concurrent) * 60 AS integral,
       countIf(concurrent > 0) AS nonzero_minutes,
       minIf(minute, concurrent > 0) AS first_active_minute,
       maxIf(minute, concurrent > 0) AS last_active_minute,
       round(sum(concurrent) * 60 / (countIf(concurrent > 0) * 60), 4) AS avg_over_active_minutes
FROM series
FORMAT TSVWithNames
