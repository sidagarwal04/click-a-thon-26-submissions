-- DAY grain · category filter · session tier.
-- category is NOT a cube level of cc_hour_agg: it rides off content_id via content_dim.
-- So the curve is rebuilt at MINUTE grain from cc_minute_delta. Deltas ARE summable
-- across dimensions, so one attribute's curve is the running sum of its own deltas;
-- each change point is weighted by how long its level HOLDS (hold_s), because
-- cc_minute_delta only stores minutes where concurrency CHANGES.
WITH change_points AS
(
    SELECT if(c.has_catalog = 0, '(unknown)', if(c.category = '', '(blank)', c.category)) AS attr,
           toStartOfHour(d.minute) AS hour,
           d.minute AS minute,
           sum(d.delta) AS dd
    FROM cc_minute_delta AS d
    LEFT ANY JOIN
    (
        SELECT content_id, category, toUInt8(1) AS has_catalog FROM content_dim FINAL
    ) AS c ON d.content_id = c.content_id
    WHERE d.minute >= '2026-07-31 00:00:00' AND d.minute < '2026-08-01 00:00:00'
    GROUP BY attr, hour, minute
),
curve AS
(
    SELECT attr, hour, minute,
           toInt64(sum(dd) OVER w_run) AS concurrent,
           leadInFrame(toUInt32(minute), 1, toUInt32(toUInt32(hour) + 3600)) OVER w_fwd
               - toUInt32(minute) AS hold_s
    FROM change_points
    WINDOW
        w_run AS (PARTITION BY attr, hour ORDER BY minute
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
        w_fwd AS (PARTITION BY attr, hour ORDER BY minute
                  ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)
)
SELECT attr AS category,
       max(concurrent) AS peak,
       argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
       sum(concurrent * hold_s) AS integral,
       round(sum(concurrent * hold_s) / 86400, 4) AS avg_concurrent,
       count() AS change_points_scanned
FROM curve
GROUP BY attr
ORDER BY peak DESC, attr ASC
LIMIT 10
FORMAT TSVWithNames
