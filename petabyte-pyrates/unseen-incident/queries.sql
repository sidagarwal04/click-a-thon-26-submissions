-- Reproducible queries for investigation evidence (gold.metric_anomalies)

-- 1) List anomalies with RCA writeback
SELECT
    toString(anomaly_id) AS anomaly_id,
    metric_hour,
    region,
    ad_format,
    metric_name,
    current_value,
    baseline_value,
    delta_pct,
    severity,
    status,
    disposition,
    rca_description
FROM gold.metric_anomalies
WHERE length(rca_description) > 0
ORDER BY metric_hour DESC;

-- 2) Confirmed vs false-positive breakdown
SELECT
    disposition,
    count() AS n,
    groupArray(metric_name) AS metrics
FROM gold.metric_anomalies
WHERE status = 'closed'
GROUP BY disposition
ORDER BY n DESC;

-- 3) Example slice drill-down for a flagged hour (replace hour/region/format)
SELECT
    slice_type,
    slice_value,
    metric_name,
    current_value,
    baseline_value,
    delta_pct
FROM gold.metric_hourly_by_slice
WHERE metric_hour = toDateTime('2026-07-10 04:30:00', 'UTC')
  AND region = 'NAM'
  AND ad_format = 'native'
  AND metric_name = 'fill_rate'
ORDER BY abs(delta_pct) DESC
LIMIT 20;

-- 4) Baseline context for same DOW/hour
SELECT *
FROM gold.baseline_hour_of_week
WHERE region = 'NAM'
  AND ad_format = 'native'
  AND metric_name = 'fill_rate'
  AND hour_of_week = toDayOfWeek(toDateTime('2026-07-10 04:30:00', 'UTC')) * 24
                  + toHour(toDateTime('2026-07-10 04:30:00', 'UTC'))
LIMIT 5;
