-- b09 — peak + time-weighted average over one day, PARTIAL platform filter (IN two values).
-- THE SHAPE THE HOUR TIER DOES NOT SERVE. sql/50_hour_agg.sql states outright that a
-- partial filter — platform IN ('ANDROID_PHONE','ANDROID_TAB') — is NOT a cube level:
-- max(peak_a, peak_b) is not the peak of a+b, they peak at different minutes. The peak
-- must be recomputed from cc_minute_delta at minute grain. This query measures exactly
-- what that documented fallback costs. Same curve arithmetic as b08.
WITH change_points AS
(
    SELECT
        toStartOfHour(minute) AS hour,
        minute,
        sum(delta) AS d
    FROM cc_minute_delta
    WHERE minute >= {p_day:DateTime}
      AND minute <  {p_day:DateTime} + INTERVAL 1 DAY
      AND platform IN {p_platforms:Array(String)}
    GROUP BY hour, minute
),
curve AS
(
    SELECT
        hour,
        minute,
        toInt64(sum(d) OVER w_run) AS concurrent,
        leadInFrame(toUInt32(minute), 1, toUInt32(toUInt32(hour) + 3600)) OVER w_fwd
            - toUInt32(minute) AS hold_s
    FROM change_points
    WINDOW
        w_run AS (PARTITION BY hour ORDER BY minute
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
        w_fwd AS (PARTITION BY hour ORDER BY minute
                  ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)
)
SELECT
    {p_platforms:Array(String)} AS platforms,
    max(concurrent) AS peak,
    argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
    sum(concurrent * hold_s) AS integral,
    round(sum(concurrent * hold_s) / 86400, 2) AS avg_concurrent,
    count() AS change_points_scanned
FROM curve
