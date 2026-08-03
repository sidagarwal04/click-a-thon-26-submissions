CREATE VIEW gold.metric_anomaly_candidates
(
    `hour` DateTime('UTC') COMMENT 'DateTime UTC of the candidate incident hour.',
    `slice_type` String COMMENT 'Same enum as gold.metric_hourly_by_slice.slice_type.',
    `slice_value` String COMMENT 'Same convention as gold.metric_hourly_by_slice.slice_value.',
    `metric` String COMMENT 'Enum: \'requests\' | \'revenue\' | \'fill_rate\' | \'ecpm\' | \'ctr\'. The five business metrics tracked. Ratios (fill_rate, ecpm, ctr) are actual = numerator/denominator over that (hour, slice).',
    `actual` Nullable(Float64) COMMENT 'Actual metric value at (hour, slice_type, slice_value). Units depend on metric: counts (requests), USD (revenue), 0..1 (fill_rate, ctr), USD-per-1000-impressions (ecpm).',
    `baseline_mean` Nullable(Float64) COMMENT 'Baseline mean from gold.baseline_hour_of_week for the matching (slice, dow(hour), hod(hour)). Same units as actual.',
    `baseline_stddev` Nullable(Float64) COMMENT 'Baseline stddev from gold.baseline_hour_of_week. Denominator of z_score.',
    `baseline_n` UInt64 COMMENT 'Number of historical samples backing the baseline (usually 2 after the switch to a 14-day window). <2 = cold-start; z_score untrusted.',
    `delta` Nullable(Float64) COMMENT 'Raw signed delta = actual - baseline_mean. Same units as actual. Positive = movement up, negative = movement down.',
    `delta_pct` Nullable(Float64) COMMENT 'Relative delta = delta / baseline_mean. Signed. -0.20 means the actual is 20% below baseline; +1.50 means 150% above.',
    `z_score` Nullable(Float64) COMMENT 'Signed z-score = delta / baseline_stddev. |z|>=4 clears Rule Z (also requires |delta_pct|>=5% magnitude floor). |z|>=6 is the critical severity threshold. Trust only when baseline_n>=2.',
    `volume_requests` UInt64 COMMENT 'Requests count at this (hour, slice). Used as noise gate for Rule R and for ranking by absolute impact.',
    `volume_impressions` UInt64 COMMENT 'Impressions count at this (hour, slice). Available for absolute revenue-impact ranking (delta_pct * volume ~ revenue miss).',
    `direction` String COMMENT 'Enum: \'up\' | \'down\'. Interpretation depends on metric: fill_rate \'down\' = supply/inventory issue (alarm); CTR \'up\' = often fraud/misclick; eCPM \'down\' = advertiser pullout; revenue \'down\' = top-line loss.',
    `flag_zscore` UInt8 COMMENT '0 or 1. Rule Z fired: |z_score|>=4 AND |delta_pct|>=0.05 AND baseline_n>=2 AND baseline_stddev>0. The 5% delta floor kills spurious criticals on ultra-tight baselines (e.g. 1.6% fill_rate moves at z=9).',
    `flag_delta_pct` UInt8 COMMENT '0 or 1. Rule R fired: |delta_pct|>=0.20 AND volume_requests >= per-slice gate (global:10000, level-1:1000, level-2:500).',
    `severity` String COMMENT 'Enum: \'critical\' | \'high\' | \'medium\' | \'low\'. Primary triage sort. critical=|z|>=6 AND |delta_pct|>=5%; high=|z|>=4 AND |delta_pct|>=5%; medium=Rule R only (large % within variance); low=neither. Kept even for \'low\' rows so the RCA engine can build a \'checked and ruled out\' narrative.'
)
COMMENT 'PRIMARY ANOMALY VIEW for the RCA engine. One row per (hour, slice_type, slice_value, metric). Joins actuals from gold.metric_hourly_by_slice to baselines from gold.baseline_hour_of_week and computes delta, delta_pct, z_score, direction, plus two independent detection flags: Rule Z (|z|>=4 AND |delta_pct|>=5% statistical deviation with magnitude floor) and Rule R (|delta_pct|>=20% relative movement with per-slice volume gate). SEVERITY: critical (|z|>=6 AND |delta_pct|>=5%), high (|z|>=4 AND |delta_pct|>=5%), medium (Rule R only), low (neither). USE: filter severity IN (\'critical\',\'high\',\'medium\') and ORDER BY abs(z_score) DESC for top-N alerts. Cross-reference with gold.metric_anomaly_stl for high-confidence anomalies (flag_zscore=1 AND flag_stl=1 = two independent methods agree). Recommended alerting bar: flag_zscore=1 AND flag_stl=1 AND volume_requests>=500 -- 96% noise reduction vs raw severity filter.'
AS WITH
    actuals AS
    (
        SELECT
            hour,
            slice_type,
            slice_value,
            toDayOfWeek(hour) AS dow,
            toHour(hour) AS hod,
            requests AS a_requests,
            revenue AS a_revenue,
            fills / nullIf(requests, 0) AS a_fill_rate,
            (revenue / nullIf(impressions, 0)) * 1000 AS a_ecpm,
            clicks / nullIf(impressions, 0) AS a_ctr,
            requests AS volume_requests,
            impressions AS volume_impressions
        FROM gold.metric_hourly_by_slice
    ),
    joined AS
    (
        SELECT
            a.hour,
            a.slice_type,
            a.slice_value,
            a.volume_requests,
            a.volume_impressions,
            b.baseline_n,
            [tuple('requests', toFloat64(a.a_requests), b.baseline_mean_requests, b.baseline_std_requests), tuple('revenue', a.a_revenue, b.baseline_mean_revenue, b.baseline_std_revenue), tuple('fill_rate', a.a_fill_rate, b.baseline_mean_fill_rate, b.baseline_std_fill_rate), tuple('ecpm', a.a_ecpm, b.baseline_mean_ecpm, b.baseline_std_ecpm), tuple('ctr', a.a_ctr, b.baseline_mean_ctr, b.baseline_std_ctr)] AS metric_bundle
        FROM
        actuals AS a
        INNER JOIN gold.baseline_hour_of_week AS b ON (b.slice_type = a.slice_type) AND (b.slice_value = a.slice_value) AND (b.dow = a.dow) AND (b.hod = a.hod)
    )
SELECT
    hour,
    slice_type,
    slice_value,
    m.1 AS metric,
    m.2 AS actual,
    m.3 AS baseline_mean,
    m.4 AS baseline_stddev,
    baseline_n,
    (m.2) - (m.3) AS delta,
    ((m.2) - (m.3)) / nullIf(m.3, 0) AS delta_pct,
    ((m.2) - (m.3)) / nullIf(m.4, 0) AS z_score,
    volume_requests,
    volume_impressions,
    if((m.2) >= (m.3), 'up', 'down') AS direction,
    if((abs(((m.2) - (m.3)) / nullIf(m.4, 0)) >= 4) AND (abs(((m.2) - (m.3)) / nullIf(m.3, 0)) >= 0.05) AND (baseline_n >= 2) AND ((m.4) > 0), 1, 0) AS flag_zscore,
    if((abs(((m.2) - (m.3)) / nullIf(m.3, 0)) >= 0.2) AND (volume_requests >= multiIf(slice_type = 'global', 10000, (slice_type IN ('region', 'ad_format', 'vertical')), 1000, (slice_type IN ('region_x_ad_format', 'region_x_vertical')), 500, 500)), 1, 0) AS flag_delta_pct,
    multiIf((abs(((m.2) - (m.3)) / nullIf(m.4, 0)) >= 6) AND (abs(((m.2) - (m.3)) / nullIf(m.3, 0)) >= 0.05) AND (baseline_n >= 2) AND ((m.4) > 0), 'critical', (abs(((m.2) - (m.3)) / nullIf(m.4, 0)) >= 4) AND (abs(((m.2) - (m.3)) / nullIf(m.3, 0)) >= 0.05) AND (baseline_n >= 2) AND ((m.4) > 0), 'high', (abs(((m.2) - (m.3)) / nullIf(m.3, 0)) >= 0.2) AND (volume_requests >= multiIf(slice_type = 'global', 10000, (slice_type IN ('region', 'ad_format', 'vertical')), 1000, (slice_type IN ('region_x_ad_format', 'region_x_vertical')), 500, 500)), 'medium', 'low') AS severity
FROM
joined
ARRAY JOIN metric_bundle AS m
