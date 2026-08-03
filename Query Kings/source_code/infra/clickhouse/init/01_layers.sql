CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS bronze.feature_specs
(
    job_id String,
    feature_slug LowCardinality(String),
    source_path String,
    spec_markdown String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (feature_slug, job_id, ingested_at);

CREATE TABLE IF NOT EXISTS bronze.feature_events
(
    job_id String,
    feature_slug LowCardinality(String),
    source_path String,
    source_line UInt64,
    event_name LowCardinality(String),
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (feature_slug, job_id, ingested_at, event_name);

CREATE TABLE IF NOT EXISTS gold.feature_metrics
(
    job_id String,
    feature_slug LowCardinality(String),
    metric_name LowCardinality(String),
    segment_key LowCardinality(String),
    segment_value String,
    metric_value Float64,
    numerator Nullable(Float64),
    denominator Nullable(Float64),
    computed_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(computed_at)
ORDER BY (feature_slug, metric_name, segment_key, segment_value, computed_at);

CREATE TABLE IF NOT EXISTS gold.feature_insights
(
    job_id String,
    feature_slug LowCardinality(String),
    insight_type LowCardinality(String),
    title String,
    summary String,
    confidence Float32,
    evidence_json String,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (feature_slug, insight_type, confidence, created_at);
