-- b06 — the dashboard curve: minute-grain concurrency for one hour, no filter.
-- Statement shape: "minute-wise ... concurrency without scanning raw session history".
-- Serving path: cc_minute_delta change points for ONE hour + hour-partitioned running
-- sum (deltas are hour-clipped per ADR 0003, so the hour is absolute — no carry-in
-- scan from t=0). Densified to all 60 minutes with WITH FILL at query time, per
-- docs/CONVENTIONS.md — the delta table itself stays sparse.
WITH change_points AS
(
    SELECT
        minute,
        sum(delta) AS d
    FROM cc_minute_delta
    WHERE minute >= {p_hour:DateTime}
      AND minute <  {p_hour:DateTime} + INTERVAL 1 HOUR
    GROUP BY minute
)
SELECT
    minute,
    concurrent
FROM
(
    SELECT
        minute,
        toInt64(sum(d) OVER (
            PARTITION BY toStartOfHour(minute)
            ORDER BY minute
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM change_points
)
ORDER BY minute ASC WITH FILL
    FROM {p_hour:DateTime}
    TO   {p_hour:DateTime} + INTERVAL 1 HOUR
    STEP toIntervalMinute(1)
INTERPOLATE (concurrent AS concurrent)
