-- Consolidated segment-level detection: trend_seasonal (volume + ratios) +
-- proportion, replaces sql/mv/08_mv_segment_detect_volume.sql,
-- 09_mv_segment_detect_ratios.sql, and 10_mv_segment_detect_proportion.sql
-- (all deleted) — same reasoning as sql/mv/03_mv_detect_global.sql: a
-- refreshable MV without APPEND fully replaces its target, so
-- inmobi.segment_anomalies can only have one writer.
--
-- No DEPENDS ON here — unlike the global chain, segment detection reads
-- inmobi.segment_metrics_hourly_v directly rather than through an
-- intermediate zr-style table, and mv_segment_metrics_hourly (sql/mv/07,
-- directly on ad_events, single hop) has been reliable under bulk loads —
-- it's only *cascaded* MVs (2+ hops from ad_events) that stall. This one
-- just runs on its own schedule and reads whatever's currently there.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_segment_detect_global
REFRESH EVERY 10 MINUTE
TO inmobi.segment_anomalies
AS

-- trend_seasonal on requests/revenue (volume metrics, detrended by a
-- trailing 7-day daily total before seasonal scoring).
SELECT x.dimension AS dimension, x.segment AS segment, x.metric AS metric, x.time_window AS time_window,
  x.observed AS observed, x.expected AS expected, x.delta AS delta, x.pct_delta AS pct_delta,
  x.z AS z, toUInt16(x.baseline_n) AS baseline_n, 'trend_seasonal' AS method
FROM (
  WITH daily AS (
    SELECT dimension, segment, d, any(dow) AS dow, sum(requests) AS req_total, sum(revenue) AS rev_total
    FROM inmobi.segment_metrics_hourly_v GROUP BY dimension, segment, d
  ),
  daily_trend AS (
    SELECT dimension, segment, d, dow, req_total, rev_total,
      avg(req_total) OVER w AS req_trend,
      avg(rev_total) OVER w AS rev_trend,
      count(req_total) OVER w AS trend_n
    FROM daily
    WINDOW w AS (PARTITION BY dimension, segment ORDER BY d ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING)
  ),
  base AS (
    SELECT h.dimension AS dimension, h.segment AS segment, h.hour_ts AS hour_ts, h.d AS d, h.dow AS dow, h.hod AS hod,
      h.requests AS requests, h.revenue AS revenue,
      dt.req_trend AS req_trend, dt.rev_trend AS rev_trend, dt.trend_n AS trend_n,
      h.requests / dt.req_trend AS req_detrended,
      h.revenue  / dt.rev_trend AS rev_detrended
    FROM inmobi.segment_metrics_hourly_v h
    INNER JOIN daily_trend dt ON h.dimension = dt.dimension AND h.segment = dt.segment AND h.d = dt.d
    WHERE dt.trend_n >= 2
  ),
  req_cell_mean AS (SELECT dimension, segment, dow, hod, avg(req_detrended) AS ca FROM base GROUP BY dimension, segment, dow, hod),
  req_noise AS (SELECT b.dimension AS nd, b.segment AS ns, varSamp(b.req_detrended - cm.ca) AS v FROM base b JOIN req_cell_mean cm USING (dimension, segment, dow, hod) GROUP BY nd, ns),
  rev_cell_mean AS (SELECT dimension, segment, dow, hod, avg(rev_detrended) AS ca FROM base GROUP BY dimension, segment, dow, hod),
  rev_noise AS (SELECT b.dimension AS nd, b.segment AS ns, varSamp(b.rev_detrended - cm.ca) AS v FROM base b JOIN rev_cell_mean cm USING (dimension, segment, dow, hod) GROUP BY nd, ns),
  seasonal AS (
    SELECT *,
      avg(req_detrended) OVER w AS req_mean, varSamp(req_detrended) OVER w AS req_var,
      avg(rev_detrended) OVER w AS rev_mean, varSamp(rev_detrended) OVER w AS rev_var,
      count(req_detrended) OVER w AS baseline_n
    FROM base
    WINDOW w AS (PARTITION BY dimension, segment, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
  ),
  scored AS (
    SELECT s.*, rn.v AS req_noise_v, vn.v AS rev_noise_v,
      sqrt((baseline_n*ifNull(req_var,0) + 3*rn.v) / (baseline_n+3)) AS req_std,
      sqrt((baseline_n*ifNull(rev_var,0) + 3*vn.v) / (baseline_n+3)) AS rev_std
    FROM seasonal s
    JOIN req_noise rn ON s.dimension = rn.nd AND s.segment = rn.ns
    JOIN rev_noise vn ON s.dimension = vn.nd AND s.segment = vn.ns
  )
  SELECT dimension, segment, 'requests' AS metric, hour_ts AS time_window, requests AS observed,
    req_trend*req_mean AS expected, requests - req_trend*req_mean AS delta,
    (requests - req_trend*req_mean) / (req_trend*req_mean) AS pct_delta,
    (requests - req_trend*req_mean) / nullif(req_trend*req_std, 0) AS z,
    baseline_n
  FROM scored WHERE baseline_n >= 2 AND dimension NOT IN ('vertical', 'campaign_type')
  UNION ALL
  SELECT dimension, segment, 'revenue', hour_ts, revenue,
    rev_trend*rev_mean, revenue - rev_trend*rev_mean,
    (revenue - rev_trend*rev_mean) / (rev_trend*rev_mean),
    (revenue - rev_trend*rev_mean) / nullif(rev_trend*rev_std, 0),
    baseline_n
  FROM scored WHERE baseline_n >= 2
) x
INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'trend_seasonal' AND c.enabled = 1
WHERE abs(x.z) > c.z_threshold

UNION ALL

-- trend_seasonal on fill_rate/render_rate/ctr/ecpm/rpr.
SELECT x.dimension AS dimension, x.segment AS segment, x.metric AS metric, x.hour_ts AS time_window,
  x.value AS observed, x.mean_v AS expected, x.value - x.mean_v AS delta, (x.value - x.mean_v) / x.mean_v AS pct_delta,
  (x.value - x.mean_v) / nullif(x.std_v, 0) AS z, toUInt16(x.baseline_n) AS baseline_n, 'trend_seasonal' AS method
FROM (
  WITH ratios AS (
    SELECT dimension, segment, hour_ts, d, dow, hod,
      fills/requests AS fill_rate,
      impressions/fills AS render_rate,
      clicks/impressions AS ctr,
      revenue/impressions*1000 AS ecpm,
      revenue/requests AS rpr
    FROM inmobi.segment_metrics_hourly_v
  ),
  unpivoted AS (
    SELECT dimension, segment, hour_ts, d, dow, hod, 'fill_rate' AS metric, fill_rate AS value FROM ratios WHERE dimension NOT IN ('vertical', 'campaign_type')
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'render_rate', render_rate FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'ctr', ctr FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'ecpm', ecpm FROM ratios
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'rpr', rpr FROM ratios WHERE dimension NOT IN ('vertical', 'campaign_type')
  ),
  cell_mean AS (SELECT dimension, segment, metric, dow, hod, avg(value) AS ca FROM unpivoted GROUP BY dimension, segment, metric, dow, hod),
  noise AS (
    SELECT u.dimension AS dimension, u.segment AS segment, u.metric AS metric, varSamp(u.value - cm.ca) AS v
    FROM unpivoted u JOIN cell_mean cm USING (dimension, segment, metric, dow, hod)
    GROUP BY u.dimension, u.segment, u.metric
  ),
  seasonal AS (
    SELECT *,
      avg(value) OVER w AS mean_v, varSamp(value) OVER w AS var_v,
      count(value) OVER w AS baseline_n
    FROM unpivoted
    WINDOW w AS (PARTITION BY dimension, segment, metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
  )
  SELECT s.*, n.v AS noise_v,
    sqrt((baseline_n*ifNull(var_v,0) + 3*n.v) / (baseline_n+3)) AS std_v
  FROM seasonal s JOIN noise n USING (dimension, segment, metric)
) x
INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'trend_seasonal' AND c.enabled = 1
WHERE x.baseline_n >= 2
  AND abs((x.value-x.mean_v)/nullif(x.std_v,0)) > c.z_threshold

UNION ALL

-- proportion (count-aware two-proportion test) on fill_rate/render_rate/ctr.
SELECT x.dimension AS dimension, x.segment AS segment, x.metric AS metric, x.hour_ts AS time_window,
  x.observed_rate AS observed, x.p0 AS expected, x.observed_rate - x.p0 AS delta, (x.observed_rate - x.p0) / x.p0 AS pct_delta,
  (x.observed_rate - x.p0) / sqrt(x.p0 * (1 - x.p0) / x.den) AS z, toUInt16(x.baseline_n) AS baseline_n, 'proportion' AS method
FROM (
  WITH counts AS (
    SELECT dimension, segment, hour_ts, d, dow, hod,
      fills AS fill_num, requests AS fill_den,
      impressions AS render_num, fills AS render_den,
      clicks AS click_num, impressions AS click_den
    FROM inmobi.segment_metrics_hourly_v
  ),
  unpivoted AS (
    SELECT dimension, segment, hour_ts, d, dow, hod, 'fill_rate' AS metric, fill_num AS num, fill_den AS den FROM counts WHERE dimension NOT IN ('vertical', 'campaign_type')
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'render_rate', render_num, render_den FROM counts
    UNION ALL SELECT dimension, segment, hour_ts, d, dow, hod, 'ctr', click_num, click_den FROM counts
  )
  SELECT *, num/den AS observed_rate,
    avg(num/den) OVER w AS p0,
    count(num) OVER w AS baseline_n
  FROM unpivoted
  WINDOW w AS (PARTITION BY dimension, segment, metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
) x
INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'proportion' AND c.enabled = 1
WHERE x.baseline_n >= 2
  -- p0 in (0,1) and den>0: a sparse low-volume segment can have a baseline
  -- rate of exactly 0 or 1 across all trailing samples — the two-proportion
  -- test is degenerate there (z = ±inf), not a real signal.
  AND x.p0 > 0 AND x.p0 < 1 AND x.den > 0
  AND abs((x.observed_rate-x.p0) / sqrt(x.p0*(1-x.p0)/x.den)) > c.z_threshold;
