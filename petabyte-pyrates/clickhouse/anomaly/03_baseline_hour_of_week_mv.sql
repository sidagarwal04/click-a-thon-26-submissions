-- Hourly refresh: recompute baselines from metric_hourly_by_slice over the trailing 14-day window.
-- REPLACE mode overwrites the table each run so downstream joins stay point-in-time consistent.

CREATE MATERIALIZED VIEW gold.baseline_hour_of_week_mv
REFRESH EVERY 1 HOUR
TO gold.baseline_hour_of_week
COMMENT 'Internal pipeline object — refreshes gold.baseline_hour_of_week every hour. Not intended to be queried directly. Run SYSTEM REFRESH VIEW gold.baseline_hour_of_week_mv after bulk loads.'
AS
WITH (
    SELECT max(hour)
    FROM gold.metrics_hourly
) AS anchor
SELECT
    slice_type,
    slice_value,
    toDayOfWeek(hour) AS dow,
    toHour(hour) AS hod,
    count() AS baseline_n,
    avg(requests) AS baseline_mean_requests,
    stddevPop(requests) AS baseline_std_requests,
    medianExact(requests) AS baseline_median_requests,
    avg(revenue) AS baseline_mean_revenue,
    stddevPop(revenue) AS baseline_std_revenue,
    medianExact(revenue) AS baseline_median_revenue,
    avg(fills / nullIf(requests, 0)) AS baseline_mean_fill_rate,
    stddevPop(fills / nullIf(requests, 0)) AS baseline_std_fill_rate,
    medianExact(fills / nullIf(requests, 0)) AS baseline_median_fill_rate,
    avg((revenue / nullIf(impressions, 0)) * 1000) AS baseline_mean_ecpm,
    stddevPop((revenue / nullIf(impressions, 0)) * 1000) AS baseline_std_ecpm,
    medianExact((revenue / nullIf(impressions, 0)) * 1000) AS baseline_median_ecpm,
    avg(clicks / nullIf(impressions, 0)) AS baseline_mean_ctr,
    stddevPop(clicks / nullIf(impressions, 0)) AS baseline_std_ctr,
    medianExact(clicks / nullIf(impressions, 0)) AS baseline_median_ctr
FROM gold.metric_hourly_by_slice
WHERE (hour >= (anchor - toIntervalDay(15))) AND (hour < (anchor - toIntervalDay(1)))
GROUP BY
    slice_type,
    slice_value,
    dow,
    hod;
