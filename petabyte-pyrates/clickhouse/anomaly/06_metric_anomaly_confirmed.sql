CREATE VIEW gold.metric_anomaly_confirmed
(
    `hour` DateTime('UTC') COMMENT 'DateTime UTC of the confirmed anomaly hour. Truncated to :00:00. Series is naturally bounded by metric_anomaly_stl\'s 14-day window since STL is joined INNER.',
    `slice_type` String COMMENT 'Same enum as gold.metric_hourly_by_slice.slice_type: global | region | ad_format | vertical | region_x_ad_format | region_x_vertical.',
    `slice_value` String COMMENT 'Same convention as gold.metric_hourly_by_slice.slice_value: \'__ALL__\' for global; single dim value for level-1; \'dim1|dim2\' for level-2.',
    `metric` String COMMENT 'Enum: \'requests\' | \'revenue\' | \'fill_rate\' | \'ecpm\' | \'ctr\'. Which of the 5 tracked metrics is confirmed anomalous.',
    `actual` Nullable(Float64) COMMENT 'Metric value at (hour, slice_type, slice_value). Units depend on metric: counts (requests), USD (revenue), 0..1 (fill_rate, ctr), USD-per-1000-impressions (ecpm).',
    `baseline_mean` Nullable(Float64) COMMENT 'Baseline mean from gold.baseline_hour_of_week for the matching (slice, dow(hour), hod(hour)). Same units as actual.',
    `baseline_stddev` Nullable(Float64) COMMENT 'Baseline population stddev from gold.baseline_hour_of_week. Denominator of z_score.',
    `baseline_n` UInt64 COMMENT 'Number of historical samples backing the baseline (typically 2 under the 14-day window). Guaranteed >= 2 for every row in this view (Rule Z\'s gate).',
    `delta` Nullable(Float64) COMMENT 'Raw signed delta = actual - baseline_mean. Same units as actual. Positive = movement up, negative = movement down.',
    `delta_pct` Nullable(Float64) COMMENT 'Relative delta = delta / baseline_mean. Signed. Guaranteed |delta_pct| >= 0.05 for every row (Rule Z magnitude floor).',
    `z_score` Nullable(Float64) COMMENT 'Signed z-score = delta / baseline_stddev. Guaranteed |z_score| >= 4 for every row (Rule Z threshold).',
    `volume_requests` UInt64 COMMENT 'Requests at this (hour, slice). Guaranteed >= per-slice volume gate (global:10000, level-1:1000, level-2:500).',
    `volume_impressions` UInt64 COMMENT 'Impressions at this (hour, slice). Available for absolute-impact ranking: |delta_pct| * volume_impressions ~ USD miss.',
    `direction` String COMMENT 'Enum: \'up\' | \'down\'. Interpretation depends on metric: fill_rate \'down\' = supply/inventory issue (alarm); CTR \'up\' = often fraud/misclick; eCPM \'down\' = advertiser pullout; revenue \'down\' = top-line loss.',
    `flag_zscore` UInt8 COMMENT '0 or 1. Rule Z fired in metric_anomaly_candidates. Guaranteed = 1 in this view (part of the WHERE clause).',
    `flag_delta_pct` UInt8 COMMENT '0 or 1. Rule R fired in metric_anomaly_candidates. Independent from the confidence tier — surfaces here so callers can see whether both rules agree.',
    `flag_stl` UInt8 COMMENT '0 or 1. Rule STL fired in metric_anomaly_stl (|z_stl|>=3 on the residual after STL decomposition, period=24). Guaranteed = 1 in this view.',
    `flag_tukey` UInt8 COMMENT '0 or 1. Rule TUK fired in metric_anomaly_stl (Tukey\'s fences on residuals). When 1, promotes confidence_tier to triple_agree.',
    `z_stl` Nullable(Float64) COMMENT 'Signed z-score on the STL residual: residual / stddevPop(residual). Rule STL threshold: |z_stl|>=3.',
    `tukey_score` Float64 COMMENT 'seriesOutliersDetectTukey output on the STL residual. 0 = not an outlier; positive = distance beyond [Q1-1.5*IQR, Q3+1.5*IQR]. Non-parametric — works for heavy-tailed CTR/eCPM.',
    `residual` Float32 COMMENT 'STL residual = actual - (seasonal + trend), period=24. The true anomaly signal after daily seasonality and slow drift are subtracted.',
    `confidence_tier` String COMMENT 'Enum: \'triple_agree\' | \'double_agree\' | \'other\'. triple_agree = Rule Z + Rule STL + Rule TUK all fire (three independent methods agree); double_agree = Rule Z + Rule STL fire (the default confidence floor of this view). ORDER BY confidence_tier ASC ranks triple_agree first alphabetically.',
    `severity_strict` String COMMENT 'Enum: \'critical\' | \'high\' | \'medium\'. Re-derived from z_score + delta_pct so callers can filter without joining back to metric_anomaly_candidates. critical=|z|>=6 AND |delta_pct|>=5%; high=|z|>=4 AND |delta_pct|>=5%; medium=neither (only reachable if the source severity bucketing changes).'
)
COMMENT 'ALERTING-GRADE anomaly view. Encodes the strict recipe from anomaly_rules.md §11.4: candidate must clear Rule Z (|z|>=4 AND |delta_pct|>=5% AND baseline_n>=2) AND Rule STL agrees (|z_stl|>=3 on STL residual) AND per-slice volume gate (global:10000, level-1:1000, level-2:500 requests). One row per (hour, slice_type, slice_value, metric) that survives all three filters. Adds two derived columns: confidence_tier (double_agree = Z+STL fired; triple_agree = Z+STL+TUK all fired) and severity_strict (critical = |z|>=6 AND |delta_pct|>=5%; high = |z|>=4 AND |delta_pct|>=5%; medium otherwise). USE: page-worthy alert queue — filter WHERE hour >= now() - INTERVAL 24 HOUR AND confidence_tier IN (\'double_agree\',\'triple_agree\') ORDER BY severity_strict, abs(z_score)+abs(z_stl) DESC. Reduces raw critical+high (~678 rows / 48h) to ~4 rows / 48h — a 99% noise reduction while preserving 3-way-agreement anomalies (CTR spikes on ad_format=interstitial, region=NAM, eCPM lift on vertical=finance in the current corpus). Consumes: metric_anomaly_candidates, metric_anomaly_stl.'
AS SELECT
    c.hour,
    c.slice_type,
    c.slice_value,
    c.metric,
    c.actual,
    c.baseline_mean,
    c.baseline_stddev,
    c.baseline_n,
    c.delta,
    c.delta_pct,
    c.z_score,
    c.volume_requests,
    c.volume_impressions,
    c.direction,
    c.flag_zscore,
    c.flag_delta_pct,
    s.flag_stl,
    s.flag_tukey,
    s.z_stl,
    s.tukey_score,
    s.residual,
    multiIf((c.flag_zscore = 1) AND (s.flag_stl = 1) AND (s.flag_tukey = 1), 'triple_agree', (c.flag_zscore = 1) AND (s.flag_stl = 1), 'double_agree', 'other') AS confidence_tier,
    multiIf((abs(c.z_score) >= 6) AND (abs(c.delta_pct) >= 0.05), 'critical', (abs(c.z_score) >= 4) AND (abs(c.delta_pct) >= 0.05), 'high', 'medium') AS severity_strict
FROM gold.metric_anomaly_candidates AS c
INNER JOIN gold.metric_anomaly_stl AS s ON (s.hour = c.hour) AND (s.slice_type = c.slice_type) AND (s.slice_value = c.slice_value) AND (s.metric = c.metric)
WHERE (c.flag_zscore = 1) AND (s.flag_stl = 1) AND (c.volume_requests >= multiIf(c.slice_type = 'global', 10000, (c.slice_type IN ('region', 'ad_format', 'vertical')), 1000, (c.slice_type IN ('region_x_ad_format', 'region_x_vertical')), 500, 500))
