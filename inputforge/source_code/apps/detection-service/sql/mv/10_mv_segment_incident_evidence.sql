-- Incident-level evidence matrix for the dashboard heatmap. For every recent
-- incident and every eligible segment in the incident metric, summarize:
--   * segment and global z-score strength during the incident,
--   * correlation during the incident (when at least two paired hours exist),
--   * correlation during the preceding 28 days,
--   * direction agreement and the count of quiet (|z| < 1) incident hours.
--
-- Correlation is computed on standardized seasonal residuals, not raw values;
-- this avoids calling two normally seasonal series "correlated" merely because
-- both rise at the same time of day. The result is evidence of co-movement,
-- not proof of causality.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_segment_incident_evidence
REFRESH EVERY 10 MINUTE
DEPENDS ON inmobi.mv_segment_zr_hourly, inmobi.mv_incidents
TO inmobi.segment_incident_evidence
AS
WITH recent_incidents AS (
  SELECT metric, start_time, end_time
  FROM inmobi.incidents
  WHERE end_time >= (
    SELECT max(hour_ts) - INTERVAL 60 DAY FROM inmobi.metric_zr_hourly
  )
),
aggregated AS (
  SELECT
    i.metric AS metric,
    i.start_time AS incident_start,
    i.end_time AS incident_end,
    s.dimension AS dimension,
    s.segment AS segment,
    argMaxIf(s.z, abs(s.z), s.hour_ts BETWEEN i.start_time AND i.end_time) AS peak_z,
    avgIf(s.z, s.hour_ts BETWEEN i.start_time AND i.end_time) AS mean_z,
    argMaxIf(g.zr, abs(g.zr), s.hour_ts BETWEEN i.start_time AND i.end_time) AS global_peak_z,
    avgIf(g.zr, s.hour_ts BETWEEN i.start_time AND i.end_time) AS global_mean_z,
    corrStableIf(g.zr, s.z, s.hour_ts BETWEEN i.start_time AND i.end_time) AS incident_corr_raw,
    countIf(s.hour_ts BETWEEN i.start_time AND i.end_time) AS incident_correlation_n,
    corrStableIf(g.zr, s.z, s.hour_ts >= i.start_time - INTERVAL 28 DAY AND s.hour_ts < i.start_time) AS baseline_corr_raw,
    countIf(s.hour_ts >= i.start_time - INTERVAL 28 DAY AND s.hour_ts < i.start_time) AS baseline_correlation_n,
    avgIf(toFloat64(sign(g.zr) = sign(s.z)), s.hour_ts BETWEEN i.start_time AND i.end_time) AS direction_match_pct,
    countIf(s.hour_ts BETWEEN i.start_time AND i.end_time) AS scored_hours,
    countIf(s.hour_ts BETWEEN i.start_time AND i.end_time AND abs(s.z) < 1) AS quiet_hours
  FROM recent_incidents AS i
  INNER JOIN inmobi.segment_zr_hourly AS s
    ON s.metric = i.metric
    AND s.hour_ts >= i.start_time - INTERVAL 28 DAY
    AND s.hour_ts <= i.end_time
  INNER JOIN inmobi.metric_zr_hourly AS g
    ON g.metric = s.metric AND g.hour_ts = s.hour_ts
  GROUP BY i.metric, i.start_time, i.end_time, s.dimension, s.segment
  HAVING scored_hours > 0
)
SELECT
  now() AS refreshed_at,
  metric,
  incident_start,
  incident_end,
  dimension,
  segment,
  peak_z,
  mean_z,
  global_peak_z,
  global_mean_z,
  if(incident_correlation_n >= 2 AND isFinite(incident_corr_raw), incident_corr_raw, NULL) AS incident_correlation,
  toUInt16(incident_correlation_n) AS incident_correlation_n,
  if(baseline_correlation_n >= 2 AND isFinite(baseline_corr_raw), baseline_corr_raw, NULL) AS baseline_correlation,
  toUInt16(baseline_correlation_n) AS baseline_correlation_n,
  direction_match_pct,
  toUInt16(scored_hours) AS scored_hours,
  toUInt16(quiet_hours) AS quiet_hours
FROM aggregated;
