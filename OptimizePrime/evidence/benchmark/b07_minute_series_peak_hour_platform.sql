-- b07 — the dashboard curve with a platform filter: minute grain, one hour, one platform.
-- Statement shape: "dashboard-grade latency on minute-grain queries WITH FILTERS".
-- Serving path: identical to b06, plus a platform equality that is the LEADING column
-- of cc_minute_delta's sort key — the filter prunes granules instead of scanning them.
WITH change_points AS
(
    SELECT
        minute,
        sum(delta) AS d
    FROM cc_minute_delta
    WHERE platform = {p_platform:String}
      AND minute >= {p_hour:DateTime}
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
