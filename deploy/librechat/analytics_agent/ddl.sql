CREATE DATABASE IF NOT EXISTS atlys_agent;

CREATE TABLE IF NOT EXISTS atlys_agent.artifacts
(
    artifact_id UUID DEFAULT generateUUIDv4(),
    run_id UUID,
    feature_slug LowCardinality(String),
    question_id String,
    artifact_type LowCardinality(String),
    source_scope Enum8(
        'none' = 0,
        'feature' = 1,
        'legacy' = 2
    ),
    content_format Enum8(
        'json' = 1,
        'csv' = 2,
        'markdown' = 3,
        'sql' = 4
    ),
    row_count UInt32 DEFAULT 0,
    content String CODEC(ZSTD(3)),
    metadata_json String CODEC(ZSTD(3)),
    content_hash FixedString(64),
    created_at DateTime64(3, 'UTC') DEFAULT now64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (
    run_id,
    question_id,
    artifact_type,
    created_at,
    artifact_id
)
TTL created_at + INTERVAL 30 DAY DELETE;
