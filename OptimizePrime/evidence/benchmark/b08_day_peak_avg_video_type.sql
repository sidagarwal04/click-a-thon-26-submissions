-- b08 — peak + time-weighted average over one day, video-type filter.
-- Statement shape: "dimension filters (... video type ...)".
-- Serving path: video_type is NOT a cube level of cc_hour_agg — it rides off
-- content_id via the catalog (sql/80_content.sql). So this is a minute-tier scan:
-- resolve the video type to its content_id set from content_dim (33,464 rows), filter
-- cc_minute_delta with IN, sum the surviving deltas (deltas ARE summable across
-- dimensions), rebuild the curve per hour, and take max / integral. Each change point
-- is weighted by how long its level HOLDS (hold_s) — summing bare change points
-- undercounts every flat stretch by a measured 3.4%.
-- (An earlier draft filtered with dictGet('dict_content', ...) = {p_video_type} in the
-- WHERE; ClickHouse 26.2.1.525 rewrites that predicate into a set lookup and fails with
-- Code 43 "Illegal type Tuple(Int64) of argument of function toInt64". The IN-subquery
-- is the same filter, and cheaper — one catalog scan instead of a per-row dictGet.)
WITH change_points AS
(
    SELECT
        toStartOfHour(minute) AS hour,
        minute,
        sum(delta) AS d
    FROM cc_minute_delta
    WHERE minute >= {p_day:DateTime}
      AND minute <  {p_day:DateTime} + INTERVAL 1 DAY
      AND content_id IN
      (
          SELECT content_id
          FROM content_dim
          WHERE video_type = {p_video_type:String}
      )
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
    {p_video_type:String} AS video_type,
    max(concurrent) AS peak,
    argMax(minute, (concurrent, -toInt64(toUInt32(minute)))) AS peak_minute,
    sum(concurrent * hold_s) AS integral,
    round(sum(concurrent * hold_s) / 86400, 2) AS avg_concurrent,
    count() AS change_points_scanned
FROM curve
