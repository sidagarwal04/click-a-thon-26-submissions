CREATE DATABASE IF NOT EXISTS featurelens_poc;

CREATE TABLE IF NOT EXISTS featurelens_poc.context_versions
(
    version UInt32,
    parent_version Int32,
    feature LowCardinality(String),
    state LowCardinality(String),
    summary String,
    trace_id String,
    payload String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY version;

CREATE TABLE IF NOT EXISTS featurelens_poc.context_nodes
(
    context_version UInt32,
    node_key String,
    node_type LowCardinality(String),
    name String,
    status LowCardinality(String),
    confidence Float32,
    properties String,
    sources Array(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (context_version, node_key);

CREATE TABLE IF NOT EXISTS featurelens_poc.context_edges
(
    context_version UInt32,
    from_key String,
    relation LowCardinality(String),
    to_key String,
    status LowCardinality(String),
    confidence Float32,
    properties String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (context_version, from_key, relation, to_key);

CREATE TABLE IF NOT EXISTS featurelens_poc.schema_registry
(
    feature String,
    context_version UInt32,
    schema_version UInt32,
    database String,
    table_name String,
    ddl String,
    status LowCardinality(String),
    trace_id String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (feature, schema_version);

CREATE TABLE IF NOT EXISTS featurelens_poc.context_conflicts
(
    context_version UInt32,
    conflict_key String,
    severity LowCardinality(String),
    description String,
    declared String,
    observed String,
    resolution String,
    status LowCardinality(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (context_version, conflict_key);

CREATE TABLE IF NOT EXISTS featurelens_poc.agent_runs
(
    run_id String,
    feature String,
    stage LowCardinality(String),
    execution_mode LowCardinality(String),
    context_version UInt32,
    trace_id String,
    payload String,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY run_id;

CREATE TABLE IF NOT EXISTS featurelens_poc.context_evaluations
(
    run_id String,
    context_version UInt32,
    evaluation String,
    score Float32,
    passed UInt8,
    details String,
    trace_id String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (run_id, evaluation);

CREATE TABLE IF NOT EXISTS featurelens_poc.context_diffs
(
    context_version UInt32,
    parent_version Int32,
    feature LowCardinality(String),
    kind LowCardinality(String),
    item_key String,
    payload String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (context_version, kind, item_key);
