-- Measured seasonal structure per monitored series — written by the profiler
-- (seriesPeriodDetectFFT / ACF / STL seasonal strength over the rollup), read by
-- both the detector (baseline model selection) and the HyperDX chart generator.
-- Re-profiled whenever a dataset loads (incl. the unseen slice): nothing about
-- seasonality is assumed, it is measured.

CREATE TABLE IF NOT EXISTS rca.series_profile
(
    dimension             LowCardinality(String),
    value                 LowCardinality(String),
    metric                LowCardinality(String),
    n_hours               UInt32,
    median_hourly_volume  Float64,   -- volume floor gate for standalone monitoring
    fft_period            Float64,   -- dominant period the data itself reports
    acf_24                Float64,
    acf_168               Float64,
    seasonal_strength_24  Float64,
    seasonal_strength_168 Float64,
    trend_slope           Float64,
    chosen_model          LowCardinality(String),  -- decision-table output, logged for explainability
    profiled_at           DateTime('UTC') DEFAULT now()
)
ENGINE = ReplacingMergeTree(profiled_at)
ORDER BY (dimension, value, metric);
