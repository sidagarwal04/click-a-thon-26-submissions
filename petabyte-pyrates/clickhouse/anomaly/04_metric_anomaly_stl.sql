CREATE VIEW gold.metric_anomaly_stl
(
    `slice_type` String COMMENT 'Same enum as gold.metric_hourly_by_slice.slice_type.',
    `slice_value` String COMMENT 'Same convention as gold.metric_hourly_by_slice.slice_value.',
    `hour` DateTime('UTC') COMMENT 'DateTime UTC. Series covers the trailing 14 days ending at max(hour) of gold.metric_hourly_by_slice.',
    `metric` String COMMENT 'Enum: \'requests\' | \'revenue\' | \'fill_rate\' | \'ecpm\' | \'ctr\'. Ratio metrics use if(denom>0, num/denom, 0) to keep the series non-nullable (STL requirement).',
    `residual` Float32 COMMENT 'STL residual = actual - (seasonal + trend) from seriesDecomposeSTL with period=24. This is the true anomaly signal after daily seasonality and slow drift are subtracted.',
    `residual_stddev` Float32 COMMENT 'Population stddev of residuals over this (slice, metric), computed via WINDOW. Denominator of z_stl. Much tighter than the raw series\' stddev because seasonality has been removed.',
    `z_stl` Nullable(Float64) COMMENT 'residual / residual_stddev. Rule STL threshold: |z_stl|>=3. Stronger than Rule Z because trend is subtracted before the z-score is computed.',
    `tukey_score` Float64 COMMENT 'Output of seriesOutliersDetectTukey applied to residuals. 0 = not an outlier by Tukey\'s fence. Positive = distance beyond [Q1-1.5*IQR, Q3+1.5*IQR]. Non-parametric -- works for heavy-tailed distributions (CTR, eCPM).',
    `flag_stl` UInt8 COMMENT '0 or 1. Rule STL fired: |z_stl|>=3.',
    `flag_tukey` UInt8 COMMENT '0 or 1. Rule TUK fired: tukey_score>0.'
)
COMMENT 'ClickHouse-native anomaly reinforcement layer using seriesDecomposeSTL + seriesOutliersDetectTukey. One row per (hour, slice_type, slice_value, metric). For each per-slice hourly series, STL strips out daily seasonality (period=24) and slow trend; the residual is the true anomaly signal. Series window: trailing 14 days. Two rules fire on the residual: Rule STL (|z_stl|>=3) and Rule TUK (Tukey\'s fences on residuals). COMPLEMENTS gold.metric_anomaly_candidates: Rule STL catches anomalies hidden by trend that Rule Z misses; Rule TUK handles non-normal distributions (CTR, eCPM have heavy tails). USE: join to metric_anomaly_candidates on (hour, slice_type, slice_value, metric); agreement of any two flags across the two views = high-confidence anomaly. Full-scan latency ~1-3 min; filter WHERE slice_type=\'...\' for interactive (~5s).'
AS WITH
    (
        SELECT max(hour)
        FROM gold.metric_hourly_by_slice
    ) AS anchor,
    series AS
    (
        SELECT
            slice_type,
            slice_value,
            arraySort(x -> (x.1), groupArray((hour, toFloat64(requests), toFloat64(revenue), if(requests > 0, toFloat64(fills) / requests, toFloat64(0)), if(impressions > 0, (toFloat64(revenue) / impressions) * 1000, toFloat64(0)), if(impressions > 0, toFloat64(clicks) / impressions, toFloat64(0))))) AS sorted
        FROM gold.metric_hourly_by_slice
        WHERE hour >= (anchor - toIntervalDay(14))
        GROUP BY
            slice_type,
            slice_value
    ),
    decomposed AS
    (
        SELECT
            slice_type,
            slice_value,
            arrayMap(x -> (x.1), sorted) AS hours,
            seriesDecomposeSTL(arrayMap(x -> (x.2), sorted), 24)[3] AS residuals_requests,
            seriesDecomposeSTL(arrayMap(x -> (x.3), sorted), 24)[3] AS residuals_revenue,
            seriesDecomposeSTL(arrayMap(x -> (x.4), sorted), 24)[3] AS residuals_fill_rate,
            seriesDecomposeSTL(arrayMap(x -> (x.5), sorted), 24)[3] AS residuals_ecpm,
            seriesDecomposeSTL(arrayMap(x -> (x.6), sorted), 24)[3] AS residuals_ctr,
            seriesOutliersDetectTukey(seriesDecomposeSTL(arrayMap(x -> (x.2), sorted), 24)[3]) AS tukey_requests,
            seriesOutliersDetectTukey(seriesDecomposeSTL(arrayMap(x -> (x.3), sorted), 24)[3]) AS tukey_revenue,
            seriesOutliersDetectTukey(seriesDecomposeSTL(arrayMap(x -> (x.4), sorted), 24)[3]) AS tukey_fill_rate,
            seriesOutliersDetectTukey(seriesDecomposeSTL(arrayMap(x -> (x.5), sorted), 24)[3]) AS tukey_ecpm,
            seriesOutliersDetectTukey(seriesDecomposeSTL(arrayMap(x -> (x.6), sorted), 24)[3]) AS tukey_ctr
        FROM
        series
    ),
    per_hour AS
    (
        SELECT
            slice_type,
            slice_value,
            hours[i] AS hour,
            residuals_requests[i] AS residual_requests,
            tukey_requests[i] AS tukey_requests,
            residuals_revenue[i] AS residual_revenue,
            tukey_revenue[i] AS tukey_revenue,
            residuals_fill_rate[i] AS residual_fill_rate,
            tukey_fill_rate[i] AS tukey_fill_rate,
            residuals_ecpm[i] AS residual_ecpm,
            tukey_ecpm[i] AS tukey_ecpm,
            residuals_ctr[i] AS residual_ctr,
            tukey_ctr[i] AS tukey_ctr
        FROM
        decomposed
        ARRAY JOIN arrayEnumerate(hours) AS i
    ),
    with_stddev AS
    (
        SELECT
            slice_type,
            slice_value,
            hour,
            residual_requests,
            stddevPop(residual_requests) OVER w AS stddev_residual_requests,
            tukey_requests,
            residual_revenue,
            stddevPop(residual_revenue) OVER w AS stddev_residual_revenue,
            tukey_revenue,
            residual_fill_rate,
            stddevPop(residual_fill_rate) OVER w AS stddev_residual_fill_rate,
            tukey_fill_rate,
            residual_ecpm,
            stddevPop(residual_ecpm) OVER w AS stddev_residual_ecpm,
            tukey_ecpm,
            residual_ctr,
            stddevPop(residual_ctr) OVER w AS stddev_residual_ctr,
            tukey_ctr
        FROM
        per_hour
        WINDOW w AS (PARTITION BY slice_type, slice_value)
    )
SELECT
    slice_type,
    slice_value,
    hour,
    m.1 AS metric,
    m.2 AS residual,
    m.3 AS residual_stddev,
    (m.2) / nullIf(m.3, 0) AS z_stl,
    m.4 AS tukey_score,
    if(abs((m.2) / nullIf(m.3, 0)) >= 3, 1, 0) AS flag_stl,
    if((m.4) > 0, 1, 0) AS flag_tukey
FROM
with_stddev
ARRAY JOIN [tuple('requests', residual_requests, stddev_residual_requests, tukey_requests), tuple('revenue', residual_revenue, stddev_residual_revenue, tukey_revenue), tuple('fill_rate', residual_fill_rate, stddev_residual_fill_rate, tukey_fill_rate), tuple('ecpm', residual_ecpm, stddev_residual_ecpm, tukey_ecpm), tuple('ctr', residual_ctr, stddev_residual_ctr, tukey_ctr)] AS m
