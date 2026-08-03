-- Store a seasonal z-score for every eligible dimension/segment/metric/hour,
-- not only threshold crossings. This is the evidence needed to distinguish
-- "measured and quiet" from "not present in segment_anomalies".
--
-- Volume metrics are detrended by the segment's trailing seven-day daily
-- total before same-(day-of-week,hour) scoring. Ratio metrics are always
-- computed sum/sum in segment_metrics_hourly_v, then scored against their
-- trailing four comparable weeks. Both use pooled residual variance shrinkage
-- so a short or low-variance cell does not produce an unstable z-score.
--
-- vertical/campaign_type cannot support requests, fill_rate, or rpr because
-- their source rows exist only after fill; those invalid combinations are
-- deliberately omitted rather than presented as evidence.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_segment_zr_hourly
REFRESH EVERY 10 MINUTE
TO inmobi.segment_zr_hourly
AS

SELECT
  now() AS computed_at,
  x.dimension AS dimension,
  x.segment AS segment,
  x.metric AS metric,
  x.hour_ts AS hour_ts,
  x.observed AS observed,
  x.expected AS expected,
  (x.observed - x.expected) / nullIf(x.expected, 0) AS pct_delta,
  x.z AS z,
  toUInt16(x.baseline_n) AS baseline_n
FROM (
  WITH daily AS (
    SELECT dimension, segment, d,
      sum(requests) AS req_total, sum(revenue) AS rev_total
    FROM inmobi.segment_metrics_hourly_v
    GROUP BY dimension, segment, d
  ),
  daily_trend AS (
    SELECT dimension, segment, d, req_total, rev_total,
      avg(req_total) OVER w AS req_trend,
      avg(rev_total) OVER w AS rev_trend,
      count(req_total) OVER w AS trend_n
    FROM daily
    WINDOW w AS (
      PARTITION BY dimension, segment ORDER BY d
      ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
    )
  ),
  base AS (
    SELECT
      h.dimension AS dimension, h.segment AS segment,
      h.hour_ts AS hour_ts, h.d AS d, h.dow AS dow, h.hod AS hod,
      h.requests AS requests, h.revenue AS revenue,
      dt.req_trend AS req_trend, dt.rev_trend AS rev_trend,
      h.requests / nullIf(dt.req_trend, 0) AS req_detrended,
      h.revenue / nullIf(dt.rev_trend, 0) AS rev_detrended
    FROM inmobi.segment_metrics_hourly_v AS h
    INNER JOIN daily_trend AS dt
      ON h.dimension = dt.dimension
      AND h.segment = dt.segment
      AND h.d = dt.d
    WHERE dt.trend_n >= 2
  ),
  req_cell_mean AS (
    SELECT dimension, segment, dow, hod, avg(req_detrended) AS cell_avg
    FROM base GROUP BY dimension, segment, dow, hod
  ),
  req_noise AS (
    SELECT b.dimension AS nd, b.segment AS ns,
      varSamp(b.req_detrended - cm.cell_avg) AS pooled_var
    FROM base AS b
    INNER JOIN req_cell_mean AS cm USING (dimension, segment, dow, hod)
    GROUP BY nd, ns
  ),
  rev_cell_mean AS (
    SELECT dimension, segment, dow, hod, avg(rev_detrended) AS cell_avg
    FROM base GROUP BY dimension, segment, dow, hod
  ),
  rev_noise AS (
    SELECT b.dimension AS nd, b.segment AS ns,
      varSamp(b.rev_detrended - cm.cell_avg) AS pooled_var
    FROM base AS b
    INNER JOIN rev_cell_mean AS cm USING (dimension, segment, dow, hod)
    GROUP BY nd, ns
  ),
  seasonal AS (
    SELECT *,
      avg(req_detrended) OVER w AS req_mean,
      varSamp(req_detrended) OVER w AS req_var,
      avg(rev_detrended) OVER w AS rev_mean,
      varSamp(rev_detrended) OVER w AS rev_var,
      count(req_detrended) OVER w AS baseline_n
    FROM base
    WINDOW w AS (
      PARTITION BY dimension, segment, dow, hod ORDER BY d
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    )
  ),
  scored AS (
    SELECT s.*,
      sqrt((baseline_n * ifNull(req_var, 0) + 3 * rn.pooled_var) / (baseline_n + 3)) AS req_std,
      sqrt((baseline_n * ifNull(rev_var, 0) + 3 * vn.pooled_var) / (baseline_n + 3)) AS rev_std
    FROM seasonal AS s
    INNER JOIN req_noise AS rn
      ON s.dimension = rn.nd AND s.segment = rn.ns
    INNER JOIN rev_noise AS vn
      ON s.dimension = vn.nd AND s.segment = vn.ns
  )
  SELECT dimension, segment, 'requests' AS metric, hour_ts,
    toFloat64(requests) AS observed,
    req_trend * req_mean AS expected,
    (requests - req_trend * req_mean) / nullIf(req_trend * req_std, 0) AS z,
    baseline_n
  FROM scored
  WHERE baseline_n >= 2 AND dimension NOT IN ('vertical', 'campaign_type')

  UNION ALL

  SELECT dimension, segment, 'revenue', hour_ts,
    revenue, rev_trend * rev_mean,
    (revenue - rev_trend * rev_mean) / nullIf(rev_trend * rev_std, 0),
    baseline_n
  FROM scored
  WHERE baseline_n >= 2
) AS x
WHERE isFinite(x.z)

UNION ALL

SELECT
  now() AS computed_at,
  x.dimension AS dimension,
  x.segment AS segment,
  x.metric AS metric,
  x.hour_ts AS hour_ts,
  x.value AS observed,
  x.mean_v AS expected,
  (x.value - x.mean_v) / nullIf(x.mean_v, 0) AS pct_delta,
  (x.value - x.mean_v) / nullIf(x.std_v, 0) AS z,
  toUInt16(x.baseline_n) AS baseline_n
FROM (
  WITH ratios AS (
    SELECT dimension, segment, hour_ts, d, dow, hod,
      fills / nullIf(requests, 0) AS fill_rate,
      impressions / nullIf(fills, 0) AS render_rate,
      clicks / nullIf(impressions, 0) AS ctr,
      revenue / nullIf(impressions, 0) * 1000 AS ecpm,
      revenue / nullIf(requests, 0) AS rpr
    FROM inmobi.segment_metrics_hourly_v
  ),
  unpivoted AS (
    SELECT dimension, segment, hour_ts, d, dow, hod,
      'fill_rate' AS metric, fill_rate AS value
    FROM ratios WHERE dimension NOT IN ('vertical', 'campaign_type')
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod,
      'render_rate', render_rate FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod,
      'ctr', ctr FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod,
      'ecpm', ecpm FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod,
      'rpr', rpr FROM ratios WHERE dimension NOT IN ('vertical', 'campaign_type')
  ),
  cell_mean AS (
    SELECT dimension, segment, metric, dow, hod, avg(value) AS cell_avg
    FROM unpivoted GROUP BY dimension, segment, metric, dow, hod
  ),
  noise AS (
    SELECT u.dimension AS dimension, u.segment AS segment, u.metric AS metric,
      varSamp(u.value - cm.cell_avg) AS pooled_var
    FROM unpivoted AS u
    INNER JOIN cell_mean AS cm USING (dimension, segment, metric, dow, hod)
    GROUP BY u.dimension, u.segment, u.metric
  ),
  seasonal AS (
    SELECT *,
      avg(value) OVER w AS mean_v,
      varSamp(value) OVER w AS var_v,
      count(value) OVER w AS baseline_n
    FROM unpivoted
    WINDOW w AS (
      PARTITION BY dimension, segment, metric, dow, hod ORDER BY d
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    )
  )
  SELECT s.*,
    sqrt((baseline_n * ifNull(var_v, 0) + 3 * n.pooled_var) / (baseline_n + 3)) AS std_v
  FROM seasonal AS s
  INNER JOIN noise AS n USING (dimension, segment, metric)
) AS x
WHERE x.baseline_n >= 2
  AND isFinite((x.value - x.mean_v) / nullIf(x.std_v, 0));
