-- Migration from the old VIEW: DROP VIEW IF EXISTS gold.baseline_hour_of_week;

CREATE TABLE gold.baseline_hour_of_week
(
    `slice_type` String COMMENT 'Same enum as gold.metric_hourly_by_slice.slice_type: global | region | ad_format | vertical | region_x_ad_format | region_x_vertical. FK-like join key.',
    `slice_value` String COMMENT 'Same convention as gold.metric_hourly_by_slice.slice_value. FK-like join key.',
    `dow` UInt8 COMMENT 'Day of week, 1..7 (Monday..Sunday, ClickHouse toDayOfWeek convention). Together with hod defines the hour-of-week bucket.',
    `hod` UInt8 COMMENT 'Hour of day 0..23 UTC.',
    `baseline_n` UInt64 COMMENT 'Number of historical samples in this (dow, hod) bucket. Typically 2 (two same-DOW hours over 14 days). baseline_n < 2 = cold-start; do not trust z-score alone.',
    `baseline_mean_requests` Float64 COMMENT 'Mean requests across the baseline_n samples for this (dow, hod) bucket. Reference value for Rule Z on requests.',
    `baseline_std_requests` Float64 COMMENT 'Population stddev of requests in this bucket. Denominator of the z-score for requests. 0 means perfectly flat history (skip Rule Z).',
    `baseline_median_requests` UInt64 COMMENT 'Median requests -- robust to past-anomaly contamination. Use as alternate reference when mean and median diverge significantly.',
    `baseline_mean_revenue` Float64 COMMENT 'Mean revenue (USD) at this (dow, hod). Rule Z reference.',
    `baseline_std_revenue` Float64 COMMENT 'Population stddev of revenue at this (dow, hod). Z-score denominator.',
    `baseline_median_revenue` Float64 COMMENT 'Median revenue -- robust to contamination.',
    `baseline_mean_fill_rate` Nullable(Float64) COMMENT 'Mean of per-hour fill_rate (fills/requests) at this (dow, hod). This is avg-of-ratios by design (each baseline sample is one hour). Differs from reporting convention (sum/sum) intentionally.',
    `baseline_std_fill_rate` Nullable(Float64) COMMENT 'Population stddev of per-hour fill_rate. Z-score denominator.',
    `baseline_median_fill_rate` Nullable(Float64) COMMENT 'Median per-hour fill_rate -- robust reference.',
    `baseline_mean_ecpm` Nullable(Float64) COMMENT 'Mean per-hour eCPM = revenue/impressions*1000 at this (dow, hod). Avg-of-ratios by design (same rationale as fill_rate baseline).',
    `baseline_std_ecpm` Nullable(Float64) COMMENT 'Population stddev of per-hour eCPM. Z-score denominator.',
    `baseline_median_ecpm` Nullable(Float64) COMMENT 'Median per-hour eCPM -- robust reference.',
    `baseline_mean_ctr` Nullable(Float64) COMMENT 'Mean per-hour CTR = clicks/impressions at this (dow, hod). Avg-of-ratios by design.',
    `baseline_std_ctr` Nullable(Float64) COMMENT 'Population stddev of per-hour CTR. Z-score denominator.',
    `baseline_median_ctr` Nullable(Float64) COMMENT 'Median per-hour CTR -- robust reference.'
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY (slice_type, slice_value, dow, hod)
COMMENT 'Per-(slice, hour-of-week) baseline statistics for anomaly detection. Populated by gold.baseline_hour_of_week_mv. One row per (slice_type, slice_value, dow, hod). Baseline window: trailing 14 days ending 24h before max(hour) -- the last day is excluded so an ongoing anomaly can''t dilute its own baseline (leave-one-out convention).'
