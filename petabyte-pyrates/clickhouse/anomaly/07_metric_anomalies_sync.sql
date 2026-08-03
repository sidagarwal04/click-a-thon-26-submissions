-- Hourly refresh: append new rows from gold.metric_anomaly_confirmed into the RCA queue.
-- Skips (metric_hour, slice_type, slice_value, metric_name) already present so agent
-- writeback (status, disposition, rca_description, evidence_json) is preserved.

CREATE MATERIALIZED VIEW gold.metric_anomalies_sync_mv
REFRESH EVERY 1 HOUR
APPEND TO gold.metric_anomalies (
    metric_hour,
    slice_type,
    slice_value,
    segment_key,
    metric_name,
    current_value,
    baseline_value,
    delta_pct,
    z_score,
    volume_requests,
    direction,
    severity,
    detection_tier,
    confidence_tier,
    status,
    disposition
)
COMMENT 'Internal pipeline object — appends new confirmed anomalies to gold.metric_anomalies every hour. Not intended to be queried directly. Deduplicates on (metric_hour, slice_type, slice_value, metric_name) so existing investigations are never re-ingested.'
AS
SELECT
    c.hour AS metric_hour,
    c.slice_type,
    c.slice_value,
    c.slice_value AS segment_key,
    c.metric AS metric_name,
    c.actual AS current_value,
    c.baseline_mean AS baseline_value,
    c.delta_pct,
    c.z_score,
    c.volume_requests,
    c.direction,
    c.severity_strict AS severity,
    'hourly_strict' AS detection_tier,
    c.confidence_tier,
    'open' AS status,
    'pending' AS disposition
FROM gold.metric_anomaly_confirmed AS c
WHERE NOT EXISTS (
    SELECT 1
    FROM gold.metric_anomalies AS m
    WHERE m.metric_hour = c.hour
      AND m.slice_type = c.slice_type
      AND m.slice_value = c.slice_value
      AND m.metric_name = c.metric
  );
