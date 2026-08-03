CREATE DATABASE IF NOT EXISTS zentra_audit;

CREATE TABLE IF NOT EXISTS zentra_audit.audit_entries
(
    entry_id UUID,
    trace_id UUID,
    span_id UUID,
    tenant_id UUID,
    investigation_id UUID,
    event_type LowCardinality(String),
    agent_id Nullable(String),
    execution_id Nullable(UUID),
    step Nullable(UInt16),
    started_at DateTime64(6, 'UTC'),
    completed_at DateTime64(6, 'UTC'),
    latency_ms UInt64,
    input_tokens UInt64,
    output_tokens UInt64,
    total_cost_usd Decimal(18, 8),
    input_hash String,
    outcome_kind Nullable(String),
    confidence Nullable(Float32),
    tools_called Array(String),
    errors Array(String),
    model Nullable(String),
    status LowCardinality(String),
    artifact_refs Array(String),
    redacted_metadata String,
    created_at DateTime64(6, 'UTC')
)
ENGINE = MergeTree
ORDER BY (tenant_id, investigation_id, created_at, entry_id);

CREATE USER IF NOT EXISTS zentra_audit_app
IDENTIFIED WITH plaintext_password BY 'zentra_audit_app';

GRANT SELECT, INSERT ON zentra_audit.audit_entries TO zentra_audit_app;
