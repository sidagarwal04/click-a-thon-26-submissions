import { executeClickHouse } from "../clickhouse.js";

export async function ensureContextTables() {
  await executeClickHouse("CREATE DATABASE IF NOT EXISTS context");

  await executeClickHouse(`
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
ORDER BY (doc_id)
`);

  await executeClickHouse(`
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
ORDER BY (feature_slug)
`);

  await executeClickHouse(`
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
ORDER BY (fact_id)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS context.contradictions
(
    id String,
    summary String,
    evidence String,
    status LowCardinality(String),
    detected_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(detected_at)
ORDER BY (id)
`);

  await executeClickHouse(`
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
ORDER BY (table_name, column_name)
`);

  await executeClickHouse(`
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
ORDER BY (feature_slug)
`);

  await executeClickHouse(`
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
ORDER BY (metric_id)
`);

  await executeClickHouse(`
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
ORDER BY (join_id)
`);

  await executeClickHouse(`
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
ORDER BY (table_name)
`);
}
