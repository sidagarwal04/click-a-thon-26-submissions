-- Consolidated global detection: trend_seasonal + proportion + day_level,
-- replaces sql/mv/03_mv_detect_trend_seasonal.sql,
-- 04_mv_detect_proportion.sql, and 05_mv_detect_day_level.sql (all deleted).
--
-- Refreshable, not reactive, and DEPENDS ON mv_zr_hourly so this only runs
-- after that view's own refresh has completed — the same fix as
-- mv_zr_hourly itself: a cascaded reactive MV isn't reliable under a bulk
-- INSERT, so this recomputes on its own schedule instead of waiting on a
-- trigger.
--
-- Consolidated into ONE MV, not three, because inmobi.anomalies now has
-- exactly one writer: a refreshable MV without APPEND does a full atomic
-- REPLACE of its target, so multiple independent refreshable MVs writing to
-- the same table would each wipe out what the others wrote. Every method
-- that writes to inmobi.anomalies has to live in this single query.
--
-- Because this recomputes full history every cycle rather than only new
-- rows, "the audit trail" now always reflects what qualifies under the
-- CURRENT detection_config, not whatever config was active when a given
-- hour first got scored. That's a deliberate improvement, not a side
-- effect — it's exactly what scripts/recompute-detections-local.ts already
-- did manually ("makes stored anomaly rows match the current MV SQL");
-- this just makes that happen automatically every refresh instead of only
-- when someone remembers to run the script.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_detect_global
REFRESH EVERY 10 MINUTE DEPENDS ON inmobi.mv_zr_hourly
TO inmobi.anomalies
AS

-- trend_seasonal: score every zr row directly.
SELECT
  z.metric AS metric, z.hour_ts AS time_window,
  CAST(NULL AS Nullable(Float64)) AS observed, CAST(NULL AS Nullable(Float64)) AS expected,
  CAST(NULL AS Nullable(Float64)) AS delta, CAST(NULL AS Nullable(Float64)) AS pct_delta,
  z.zr AS z, CAST(NULL AS Nullable(UInt16)) AS baseline_n, 'trend_seasonal' AS method
FROM inmobi.metric_zr_hourly z
INNER JOIN inmobi.detection_config c ON c.metric = z.metric AND c.method = 'trend_seasonal' AND c.enabled = 1
WHERE abs(z.zr) > c.z_threshold

UNION ALL

-- proportion: two-proportion z-test on fill_rate/render_rate/ctr, trailing
-- 4-week same-(dow,hod) baseline via window function (same shape as the
-- segment-level proportion query).
SELECT x.metric AS metric, x.hour_ts AS time_window, x.observed_rate AS observed, x.p0 AS expected,
  x.observed_rate - x.p0 AS delta, (x.observed_rate - x.p0) / x.p0 AS pct_delta,
  (x.observed_rate - x.p0) / sqrt(x.p0 * (1 - x.p0) / x.den) AS z,
  toUInt16(x.baseline_n) AS baseline_n, 'proportion' AS method
FROM (
  SELECT *, num / den AS observed_rate,
    avg(num / den) OVER w AS p0,
    count(num) OVER w AS baseline_n
  FROM (
    SELECT hour_ts, d, dow, hod, 'fill_rate' AS metric, fills AS num, requests AS den FROM inmobi.metrics_hourly_v
    UNION ALL SELECT hour_ts, d, dow, hod, 'render_rate', impressions, fills FROM inmobi.metrics_hourly_v
    UNION ALL SELECT hour_ts, d, dow, hod, 'ctr', clicks, impressions FROM inmobi.metrics_hourly_v
  )
  WINDOW w AS (PARTITION BY metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
) x
INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'proportion' AND c.enabled = 1
WHERE x.baseline_n >= 2
  -- p0 in (0,1) and den>0: a sparse low-volume cell can have a trailing
  -- baseline rate of exactly 0 or 1 — the two-proportion test is degenerate
  -- there (z = ±inf), not a real signal.
  AND x.p0 > 0 AND x.p0 < 1 AND x.den > 0
  AND abs((x.observed_rate - x.p0) / sqrt(x.p0 * (1 - x.p0) / x.den)) > c.z_threshold

UNION ALL

-- day_level: pools each completed day's 24 zr values into a one-sample
-- t-test. Only days with all 24 hours present qualify.
SELECT
  x.metric AS metric, toDateTime(x.d) AS time_window,
  x.mean_zr AS observed, 0.0 AS expected, x.mean_zr AS delta,
  CAST(NULL AS Nullable(Float64)) AS pct_delta, x.day_t AS z,
  toUInt16(x.n) AS baseline_n, 'day_level' AS method
FROM (
  SELECT metric, d, count() AS n, avg(zr) AS mean_zr, avg(zr) * sqrt(count()) AS day_t
  FROM inmobi.metric_zr_hourly
  GROUP BY metric, d
  HAVING n = 24
) x
INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'day_level' AND c.enabled = 1
WHERE abs(x.day_t) > c.z_threshold;
