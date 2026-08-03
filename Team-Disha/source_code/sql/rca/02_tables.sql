-- RCA result tables (batch-materialized). Truncated/refilled by later scripts.

CREATE TABLE IF NOT EXISTS rca_thresholds
(
    name String,
    value Float64
)
ENGINE = MergeTree
ORDER BY name;

TRUNCATE TABLE rca_thresholds;
INSERT INTO rca_thresholds VALUES
    ('thresh_req_chg', 0.15),
    ('thresh_fill_chg', 0.015),
    ('thresh_ecpm_chg', 0.04),
    ('thresh_rev_chg', 0.03),
    ('seg_fill_chg', 0.10),
    ('seg_fill_impact', 1500),
    ('seg_ecpm_abs', 0.25),
    ('seg_ecpm_rev', 3.0),
    ('min_seg_req', 2000);

DROP TABLE IF EXISTS rca_daily_wow;
CREATE TABLE rca_daily_wow
(
    event_date Date,
    baseline_day Date,
    baseline_rule LowCardinality(String) DEFAULT 'same_dow_minus_7',
    requests UInt64,
    fills UInt64,
    impressions UInt64,
    clicks UInt64,
    revenue Float64,
    fill_rate Nullable(Float64),
    ecpm Nullable(Float64),
    ctr Nullable(Float64),
    rpr Nullable(Float64),
    base_requests UInt64,
    base_fills UInt64,
    base_impressions UInt64,
    base_clicks UInt64,
    base_revenue Float64,
    base_fill_rate Nullable(Float64),
    base_ecpm Nullable(Float64),
    base_ctr Nullable(Float64),
    base_rpr Nullable(Float64),
    req_chg Nullable(Float64),
    rev_chg Nullable(Float64),
    fill_chg Nullable(Float64),
    ecpm_chg Nullable(Float64),
    flag_volume UInt8,
    flag_fill UInt8,
    flag_ecpm UInt8,
    flag_revenue UInt8,
    is_anomaly UInt8,
    -- Seasonality residual vs prior same-DOW weeks (ClickHouse window stats)
    z_requests Float64 DEFAULT 0,
    z_revenue Float64 DEFAULT 0,
    z_fill Float64 DEFAULT 0,
    z_ecpm Float64 DEFAULT 0,
    seasonal_history_n UInt8 DEFAULT 0,
    seasonal_ok UInt8 DEFAULT 1,
    is_anomaly_gated UInt8 DEFAULT 0,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY event_date;

CREATE TABLE IF NOT EXISTS rca_factor_day
(
    event_date Date,
    baseline_day Date,
    primary_factor LowCardinality(String),
    share_requests Float64,
    share_fill_rate Float64,
    share_ecpm Float64,
    rel_requests Float64,
    rel_fill_rate Float64,
    rel_ecpm Float64,
    is_recovery_volume UInt8,
    is_recovery_fill UInt8,
    is_recovery_ecpm UInt8,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY event_date;

CREATE TABLE IF NOT EXISTS rca_segment_day
(
    event_date Date,
    baseline_day Date,
    dimension LowCardinality(String),
    dim_value String,
    segment String,
    req_t UInt64,
    req_b UInt64,
    fills_t UInt64,
    fills_b UInt64,
    imp_t UInt64,
    imp_b UInt64,
    rev_t Float64,
    rev_b Float64,
    fill_t Nullable(Float64),
    fill_b Nullable(Float64),
    fill_chg Float64,
    ecpm_t Nullable(Float64),
    ecpm_b Nullable(Float64),
    ecpm_chg Float64,
    req_chg Float64,
    d_rev Float64,
    fill_impact Float64,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, dimension, dim_value);

CREATE TABLE IF NOT EXISTS rca_combo_day
(
    event_date Date,
    baseline_day Date,
    combo_kind LowCardinality(String),
    segment String,
    req_t UInt64,
    req_b UInt64,
    fills_t UInt64,
    fills_b UInt64,
    imp_t UInt64,
    imp_b UInt64,
    rev_t Float64,
    rev_b Float64,
    fill_t Nullable(Float64),
    fill_b Nullable(Float64),
    fill_chg Float64,
    ecpm_t Nullable(Float64),
    ecpm_b Nullable(Float64),
    ecpm_chg Float64,
    req_chg Float64,
    d_rev Float64,
    fill_impact Float64,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, combo_kind, segment);

CREATE TABLE IF NOT EXISTS rca_day_signals
(
    event_date Date,
    primary_factor LowCardinality(String),
    shape LowCardinality(String),
    segment_key String,
    segment String,
    source LowCardinality(String),
    severity Float64,
    hidden_globally UInt8,
    evidence_json String,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, primary_factor, segment_key);

DROP TABLE IF EXISTS rca_incidents;
CREATE TABLE rca_incidents
(
    id String,
    window_start Date,
    window_end Date,
    n_days UInt32,
    probe_day Date,
    baseline_day Date,
    baseline_rule LowCardinality(String) DEFAULT 'same_dow_minus_7',
    primary_factor LowCardinality(String),
    shape LowCardinality(String),
    segment String,
    source LowCardinality(String),
    hidden_globally UInt8,
    severity Float64,
    req_chg Nullable(Float64),
    rev_chg Nullable(Float64),
    fill_chg Nullable(Float64),
    ecpm_chg Nullable(Float64),
    share_requests Nullable(Float64),
    share_fill_rate Nullable(Float64),
    share_ecpm Nullable(Float64),
    evidence_json String,
    ruled_out Array(String),
    explanation String,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (window_start, id);

DROP TABLE IF EXISTS rca_ml_expected;
CREATE TABLE rca_ml_expected
(
    event_date Date,
    -- simpleLinearRegression(T-7 baseline -> actual): y = slope * x + intercept
    rev_actual Float64,
    rev_t7 Float64,
    rev_expected Float64,
    rev_residual Float64,
    rev_residual_z Float64,
    rev_slope Float64,
    rev_intercept Float64,
    fill_actual Float64,
    fill_t7 Float64,
    fill_expected Float64,
    fill_residual Float64,
    fill_residual_z Float64,
    fill_slope Float64,
    fill_intercept Float64,
    req_actual Float64,
    req_t7 Float64,
    req_expected Float64,
    req_residual Float64,
    req_residual_z Float64,
    req_slope Float64,
    req_intercept Float64,
    ml_outlier UInt8,
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY event_date;

DROP TABLE IF EXISTS rca_counterfactual;
CREATE TABLE rca_counterfactual
(
    incident_id String,
    probe_day Date,
    baseline_day Date,
    primary_factor LowCardinality(String),
    segment String,
    requests_t UInt64,
    fill_t Float64,
    ecpm_t Float64,
    revenue_actual Float64,
    base_requests UInt64,
    base_fill Float64,
    base_ecpm Float64,
    base_revenue Float64,
    revenue_if_fill_at_baseline Float64,
    revenue_if_ecpm_at_baseline Float64,
    revenue_if_requests_at_baseline Float64,
    delta_if_fill_fixed Float64,
    delta_if_ecpm_fixed Float64,
    delta_if_requests_fixed Float64,
    delta_explained_by_primary Float64,
    ruled_out_factors Array(String),
    built_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (incident_id, probe_day);
