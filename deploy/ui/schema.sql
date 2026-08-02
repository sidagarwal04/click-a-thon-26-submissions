CREATE DATABASE IF NOT EXISTS agent;

CREATE TABLE IF NOT EXISTS agent.investigations
(
    investigation_id UUID,
    revision UInt64,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    events_blob_uri String,
    events_filename String,
    events_bytes UInt64,
    events_sha256 FixedString(64),
    spec_blob_uri String,
    spec_filename String,
    spec_bytes UInt64,
    spec_sha256 FixedString(64),
    status LowCardinality(String),
    current_agent LowCardinality(String),
    progress String,
    final_result String,
    error_message String
)
ENGINE = MergeTree
ORDER BY (investigation_id, revision);

CREATE TABLE IF NOT EXISTS agent.investigation_agent_status
(
    investigation_id UUID,
    agent_name LowCardinality(String),
    revision UInt64,
    status LowCardinality(String),
    progress String,
    result String,
    error_message String,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (investigation_id, agent_name, revision);

-- A stable feature identity is optional for legacy submissions but required to
-- compare schemas across separate investigation-scoped physical object names.
ALTER TABLE agent.investigations ADD COLUMN IF NOT EXISTS feature_key String DEFAULT '' AFTER investigation_id;

-- Physical ClickHouse schema history is collected by the Context Store during
-- context refresh. These records are append-only snapshots, not mutable schema
-- state: exact DDL is retained for audit and normalized metadata is used for
-- deterministic comparisons.
CREATE TABLE IF NOT EXISTS agent.schema_versions
(
    schema_version_id UUID,
    previous_schema_version_id Nullable(UUID),
    feature_key String,
    logical_role String,
    object_kind LowCardinality(String),
    database_name LowCardinality(String),
    object_name String,
    investigation_id Nullable(UUID),
    observed_at DateTime64(3, 'UTC'),
    verification_status LowCardinality(String),
    normalized_fingerprint FixedString(64),
    exact_ddl String CODEC(ZSTD(3)),
    metadata_json String CODEC(ZSTD(3)),
    evidence_query_ids Array(String)
)
ENGINE = MergeTree
ORDER BY (feature_key, logical_role, observed_at, schema_version_id);

CREATE TABLE IF NOT EXISTS agent.schema_columns
(
    schema_version_id UUID,
    position UInt16,
    column_name String,
    column_type String,
    default_kind LowCardinality(String),
    default_expression String,
    codec_expression String,
    comment String,
    column_fingerprint FixedString(64)
)
ENGINE = MergeTree
ORDER BY (schema_version_id, position, column_name);

CREATE TABLE IF NOT EXISTS agent.schema_changes
(
    schema_change_id UUID,
    schema_version_id UUID,
    previous_schema_version_id Nullable(UUID),
    feature_key String,
    logical_role String,
    operation LowCardinality(String),
    impact LowCardinality(String),
    before_json String CODEC(ZSTD(3)),
    after_json String CODEC(ZSTD(3)),
    investigation_id Nullable(UUID),
    evidence_query_ids Array(String),
    observed_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (feature_key, logical_role, observed_at, schema_change_id);

-- Immutable, database-backed history for the Context Agent.  The Markdown file
-- remains the readable latest snapshot; these tables are the durable audit and
-- retrieval store.  `version_number` is assigned by the Context Agent and is
-- never updated or reused.
CREATE TABLE IF NOT EXISTS agent.business_logic_versions
(
    context_id UUID,
    version_number UInt64,
    previous_context_id Nullable(UUID),
    status Enum8('published' = 1, 'superseded' = 2, 'proposed' = 3, 'conflicted' = 4, 'not_persisted' = 5),
    effective_at DateTime64(3, 'UTC'),
    published_at DateTime64(3, 'UTC'),
    content_sha256 FixedString(64),
    snapshot_markdown String CODEC(ZSTD(3)),
    snapshot_json String CODEC(ZSTD(3)),
    change_summary String CODEC(ZSTD(3)),
    source_run_id Nullable(UUID),
    source_query_ids Array(String),
    embedding_model LowCardinality(String),
    embedding_dimensions UInt16,
    created_by LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(published_at)
ORDER BY (published_at, version_number, context_id)
SETTINGS index_granularity = 8192;

-- One row per semantically coherent context section per immutable version.
-- The initial embedding contract uses text-embedding-3-small (1536 dimensions).
-- If the model changes, write to a new table with its exact dimension rather
-- than mixing vector lengths in this index.
CREATE TABLE IF NOT EXISTS agent.business_logic_embeddings_v1
(
    context_id UUID,
    version_number UInt64,
    chunk_id UUID,
    chunk_ordinal UInt16,
    section_type LowCardinality(String),
    entity_type LowCardinality(String),
    entity_id String,
    valid_from DateTime64(3, 'UTC'),
    valid_to Nullable(DateTime64(3, 'UTC')),
    status LowCardinality(String),
    confidence Float32,
    content_sha256 FixedString(64),
    chunk_text String CODEC(ZSTD(3)),
    metadata_json String CODEC(ZSTD(3)),
    embedding Array(Float32) CODEC(NONE),
    INDEX embedding_hnsw embedding TYPE vector_similarity('hnsw', 'cosineDistance', 1536) GRANULARITY 100000000
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(valid_from)
ORDER BY (section_type, entity_type, entity_id, version_number, chunk_ordinal, chunk_id)
SETTINGS index_granularity = 8192;

-- Semantic, object-level context changelog. The full immutable context remains
-- in business_logic_versions; this table is the bounded diff/read model.
CREATE TABLE IF NOT EXISTS agent.context_changes
(
    context_change_id UUID,
    context_id UUID,
    previous_context_id Nullable(UUID),
    version_number UInt64,
    domain LowCardinality(String),
    object_id String,
    operation LowCardinality(String),
    before_json String CODEC(ZSTD(3)),
    after_json String CODEC(ZSTD(3)),
    reason String CODEC(ZSTD(3)),
    evidence_refs Array(String),
    confidence Float32,
    review_required Bool,
    schema_version_ids Array(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (version_number, domain, object_id, context_change_id);

-- Immutable Finalizer delivery history. The envelope is retained verbatim for
-- replay/audit while the companion items table serves fast UI/API queries.
CREATE TABLE IF NOT EXISTS agent.finalizer_results
(
    result_id UUID,
    investigation_id UUID,
    revision UInt64,
    run_id Nullable(UUID),
    status LowCardinality(String),
    generated_at DateTime64(3, 'UTC'),
    envelope_sha256 FixedString(64),
    envelope_json String CODEC(ZSTD(3)),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (investigation_id, revision, result_id);

CREATE TABLE IF NOT EXISTS agent.finalizer_result_items
(
    result_id UUID,
    investigation_id UUID,
    revision UInt64,
    category LowCardinality(String),
    ordinal UInt16,
    item_id String,
    title String,
    payload_json String CODEC(ZSTD(3)),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (investigation_id, revision, category, ordinal, item_id);
