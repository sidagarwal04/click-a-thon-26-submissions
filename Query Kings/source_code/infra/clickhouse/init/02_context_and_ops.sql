CREATE DATABASE IF NOT EXISTS context;
CREATE DATABASE IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS context.context_documents
(
    doc_id String,
    doc_type LowCardinality(String),
    source_path String,
    content String,
    content_hash String,
    job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (doc_id);

CREATE TABLE IF NOT EXISTS context.feature_registry
(
    feature_slug String,
    job_id String,
    table_name String,
    primary_entity String,
    workflow_type LowCardinality(String),
    event_names_json String,
    success_event String,
    metric_hints_json String,
    validation_json String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (feature_slug);

CREATE TABLE IF NOT EXISTS context.fact_registry
(
    fact_id String,
    fact_type LowCardinality(String),
    subject String,
    predicate String,
    object String,
    confidence Float32,
    evidence_json String,
    source_job_id String,
    created_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (fact_id);

CREATE TABLE IF NOT EXISTS context.contradictions
(
    id String,
    summary String,
    evidence String,
    status LowCardinality(String),
    detected_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(detected_at)
ORDER BY (id);

CREATE TABLE IF NOT EXISTS context.column_registry
(
    feature_slug String,
    table_name String,
    column_name String,
    clickhouse_type String,
    source_path String,
    semantic_role LowCardinality(String),
    is_nullable UInt8,
    sample_values_json String,
    reason String,
    confidence Float32,
    source_job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (table_name, column_name);

CREATE TABLE IF NOT EXISTS context.workflow_registry
(
    feature_slug String,
    table_name String,
    workflow_type LowCardinality(String),
    ordered_events_json String,
    start_event String,
    success_event String,
    primary_entity String,
    primary_entity_column String,
    segment_columns_json String,
    source_job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (feature_slug);

CREATE TABLE IF NOT EXISTS context.metric_registry
(
    metric_id String,
    feature_slug String,
    metric_name String,
    formula_sql String,
    numerator_definition String,
    denominator_definition String,
    grain String,
    required_tables_json String,
    segment_columns_json String,
    caveats String,
    confidence Float32,
    source_job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (metric_id);

CREATE TABLE IF NOT EXISTS context.join_registry
(
    join_id String,
    left_table String,
    left_column String,
    right_table String,
    right_column String,
    join_type LowCardinality(String),
    grain String,
    confidence Float32,
    evidence String,
    source_job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (join_id);

CREATE TABLE IF NOT EXISTS context.schema_quality_registry
(
    feature_slug String,
    table_name String,
    engine String,
    partition_by String,
    order_by_json String,
    ttl String,
    materialized_views_json String,
    validation_json String,
    validation_passed UInt8,
    source_job_id String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (table_name);

CREATE TABLE IF NOT EXISTS ops.pipeline_runs
(
    job_id String,
    feature_slug LowCardinality(String),
    spec_folder String,
    status LowCardinality(String),
    trace_id String,
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    summary_json String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (job_id);

CREATE TABLE IF NOT EXISTS ops.pipeline_stages
(
    job_id String,
    stage_id LowCardinality(String),
    stage_name LowCardinality(String),
    status LowCardinality(String),
    input_json String,
    output_json String,
    error String,
    recorded_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (job_id, stage_id, recorded_at);

CREATE TABLE IF NOT EXISTS ops.data_loads
(
    load_id String,
    load_type LowCardinality(String),
    status LowCardinality(String),
    trace_id String,
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    summary_json String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (load_id);

CREATE TABLE IF NOT EXISTS ops.data_load_tables
(
    load_id String,
    table_name String,
    source_path String,
    expected_rows Nullable(UInt64),
    actual_rows UInt64,
    status LowCardinality(String),
    validation_json String,
    loaded_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (load_id, table_name);

CREATE TABLE IF NOT EXISTS ops.job_artifacts
(
    job_id String,
    stage LowCardinality(String),
    filename String,
    content String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (job_id, stage, filename);
