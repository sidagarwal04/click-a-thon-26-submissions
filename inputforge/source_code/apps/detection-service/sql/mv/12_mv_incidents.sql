-- Canonical incident materialization. Incident formation depends on gaps
-- across the complete anomaly history, so a normal block-triggered MV cannot
-- compute it correctly. This refreshable MV recomputes the compact result
-- every ten minutes and atomically replaces inmobi.incidents.
--
-- DEPENDS ON mv_detect_global so this only runs after that view's own
-- refresh has completed, rather than racing it on an independent timer that
-- happens to share the same 10-minute cadence — without this, mv_incidents
-- could read inmobi.anomalies mid-replace or one cycle stale.
--
-- No FINAL on inmobi.anomalies — it's plain MergeTree now (mv_detect_global
-- is its only writer, full REPLACE every refresh, no ReplacingMergeTree
-- dedup needed), and ClickHouse Cloud's SharedMergeTree rejects FINAL on a
-- non-Replacing table outright (ILLEGAL_FINAL) rather than treating it as
-- a no-op.
--
-- Only adverse rows from currently enabled detector methods participate.
-- Each statistical unit qualifies independently: an hourly detector row
-- contributes that hour, while a completed `day_level` row contributes all
-- 24 hours of that day. Adjacent/overlapping qualified units are collapsed
-- only to describe one notification window; there is no duration gate.
--
-- A narrower version of this (day_level only contributing hours that
-- individually corroborate the day's direction, |zr| >= 1) was tried and
-- reverted: it's more statistically honest about which hours actually
-- moved, but a single day_level flag's corroborating hours are rarely
-- perfectly consecutive, so the no-gap-tolerance collapsing below split one
-- real day_level detection into several small same-z "incidents" instead of
-- one — net noisier for a page-routing consumer, not less. Blind 24-hour
-- expansion is coarser per-incident but produces one incident per real
-- detection, which won this tradeoff for now.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_incidents
REFRESH EVERY 10 MINUTE DEPENDS ON inmobi.mv_detect_global
TO inmobi.incidents
AS
WITH active_rows AS (
  SELECT
    a.detected_at,
    a.metric,
    a.method,
    a.time_window,
    a.observed,
    a.expected,
    a.pct_delta,
    a.z
  FROM inmobi.anomalies AS a
  INNER JOIN inmobi.detection_config AS c
    ON c.metric = a.metric AND c.method = a.method
      AND c.enabled = 1 AND c.incident_enabled = 1
  WHERE a.z < 0
),
expanded_rows AS (
  SELECT
    a.*,
    a.time_window + toIntervalHour(offset) AS qualified_hour
  FROM active_rows AS a
  ARRAY JOIN range(if(a.method = 'day_level', 24, 1)) AS offset
),
flagged_hours AS (
  SELECT metric, qualified_hour
  FROM expanded_rows
  GROUP BY metric, qualified_hour
),
gapped AS (
  SELECT
    *,
    qualified_hour - lagInFrame(qualified_hour, 1, qualified_hour)
      OVER (PARTITION BY metric ORDER BY qualified_hour) AS gap_seconds
  FROM flagged_hours
),
members AS (
  SELECT
    metric,
    qualified_hour,
    sum(if(gap_seconds > 3600, 1, 0))
      OVER (PARTITION BY metric ORDER BY qualified_hour) AS span_id
  FROM gapped
)
SELECT
  a.metric AS metric,
  min(a.qualified_hour) AS start_time,
  max(a.qualified_hour) AS end_time,
  toUInt16(dateDiff('hour', min(a.qualified_hour), max(a.qualified_hour)) + 1) AS span_hours,
  toUInt16(uniqExact(a.qualified_hour)) AS flagged_hours,
  arraySort(groupUniqArray(a.method)) AS methods,
  max(abs(a.z)) AS max_abs_z,
  max(a.detected_at) AS detected_at,
  argMaxIf(a.observed, abs(a.z), a.observed IS NOT NULL AND a.expected IS NOT NULL AND a.pct_delta IS NOT NULL) AS observed,
  argMaxIf(a.expected, abs(a.z), a.observed IS NOT NULL AND a.expected IS NOT NULL AND a.pct_delta IS NOT NULL) AS expected,
  argMaxIf(a.pct_delta, abs(a.z), a.observed IS NOT NULL AND a.expected IS NOT NULL AND a.pct_delta IS NOT NULL) AS pct_delta,
  now() AS refreshed_at
FROM expanded_rows AS a
INNER JOIN members AS m
  ON m.metric = a.metric AND m.qualified_hour = a.qualified_hour
GROUP BY a.metric, m.span_id;
