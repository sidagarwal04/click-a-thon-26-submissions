-- s15 · MINUTE grain · no filter · the peak hour, all 60 minute buckets.
-- This is the dashboard curve. Same densify recipe as s14, one hour wide.
SELECT minute, concurrent
FROM
(
    SELECT minute,
           toInt64(sum(d) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM
    (
        SELECT minute, sum(delta) AS d
        FROM cc_minute_delta
        WHERE minute >= '2026-07-31 11:00:00' AND minute < toDateTime('2026-07-31 11:00:00') + INTERVAL 1 HOUR
        GROUP BY minute
        ORDER BY minute WITH FILL FROM toDateTime('2026-07-31 11:00:00')
                        TO toDateTime('2026-07-31 11:00:00') + INTERVAL 1 HOUR STEP toIntervalSecond(60)
    )
)
ORDER BY minute
FORMAT TSVWithNames
