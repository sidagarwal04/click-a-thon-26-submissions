-- Context layer + ops tables. Owned by Wave 0; read by the Context Agent and the dashboard.
--
-- WHY CLICKHOUSE (judges will ask):
--   1. Contradiction detection becomes deterministic SQL. The context lives in the same
--      engine as system.columns, so "base_context.md claims application_started carries
--      visa_issuance_eta_days" is settled by one query returning 0. The LLM proposes; SQL
--      adjudicates. No other storage gives you that.
--   2. Versioning, diffs and changelog are free: append-only log + LIMIT 1 BY entry_id for
--      current state; a diff between snapshots is a self-join. No bespoke version bookkeeping.
--   3. context_snapshot is the traceability primitive. Every LLM call carries a snapshot_id
--      pinning exact (entry_id, version) pairs, so a judge can replay the precise context
--      behind any insight. That answers "context freshness" with a hash, not a promise.
--   4. Zero extra infrastructure, and an honest dogfood of the mandated primary datastore.
--
-- REJECTED: a vector store. The layer is ~60-150 entries; a filtered snapshot fits in a
-- prompt under 20k chars. Embeddings would add infra and make *which* context fed a decision
-- nondeterministic -- precisely the thing we need auditable -- while improving recall by nothing.

CREATE TABLE IF NOT EXISTS context_entry_log
(
    entry_id        String,
    version         UInt32,
    kind            LowCardinality(String),
    key             String,
    body            String CODEC(ZSTD(3)),
    formula         String DEFAULT '',
    source          LowCardinality(String),
    source_ref      String DEFAULT '',
    confidence      Float32 DEFAULT 1.0,
    status          LowCardinality(String) DEFAULT 'active',
    refs            Array(String),
    body_hash       FixedString(64),
    change_reason   String DEFAULT '',
    changed_by      LowCardinality(String) DEFAULT '',
    run_id          String DEFAULT '',
    created_at      DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (entry_id, version);

-- Current state: highest version per entry, excluding retired entries.
CREATE VIEW IF NOT EXISTS context_current AS
SELECT *
FROM context_entry_log
WHERE status != 'superseded'
ORDER BY version DESC
LIMIT 1 BY entry_id;

CREATE TABLE IF NOT EXISTS context_snapshot
(
    snapshot_id        String,
    version            UInt32,
    created_at         DateTime64(3) DEFAULT now64(3),
    entry_ids          Array(String),
    entry_versions     Array(UInt32),
    entry_count        UInt32,
    schema_fingerprint String DEFAULT '',
    note               String DEFAULT '',
    run_id             String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (created_at, snapshot_id);

CREATE TABLE IF NOT EXISTS context_changelog
(
    ts           DateTime64(3) DEFAULT now64(3),
    run_id       String,
    action       LowCardinality(String),   -- added | updated | superseded
    entry_id     String,
    from_version UInt32,
    to_version   UInt32,
    summary      String,
    detail       String
)
ENGINE = MergeTree
ORDER BY (ts, entry_id);

CREATE TABLE IF NOT EXISTS contradiction
(
    contradiction_id    String,
    detected_at         DateTime64(3) DEFAULT now64(3),
    kind                LowCardinality(String),
    severity            LowCardinality(String),
    title               String,
    claim               String,
    evidence            String,
    verification_sql    String DEFAULT '',
    verification_result String DEFAULT '',
    verified            UInt8 DEFAULT 0,
    proposed_resolution String DEFAULT '',
    entry_ids           Array(String),
    detected_by         LowCardinality(String),
    run_id              String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (detected_at, contradiction_id);

-- Schema fingerprint history -> powers the "schema changes over time" view.
CREATE TABLE IF NOT EXISTS schema_snapshot_log
(
    run_id      String,
    captured_at DateTime64(3) DEFAULT now64(3),
    database    LowCardinality(String),
    table       LowCardinality(String),
    column      String,
    type        String,
    comment     String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (captured_at, database, table, column);

CREATE TABLE IF NOT EXISTS pipeline_runs
(
    run_id          String,
    ts              DateTime64(3) DEFAULT now64(3),
    feature_slug    String,
    stage           LowCardinality(String),
    status          LowCardinality(String),
    context_version UInt32,
    trace_id        String DEFAULT '',
    trace_url       String DEFAULT '',
    detail          String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (ts, run_id);

-- Human-in-the-loop schema approval. Append-only, same pattern as context_entry_log:
-- a "pending" row is written when the DDL proposal clears dry_run(), and a later
-- "approved"/"rejected" row (same run_id, later ts) is the decision -- no UPDATE, so
-- the CLI (blocking on stdin) and the Streamlit console (polling this table) can both
-- resolve the same pending row without coordinating with each other directly.
CREATE TABLE IF NOT EXISTS pipeline_approvals
(
    run_id       String,
    ts           DateTime64(3) DEFAULT now64(3),
    table_name   String,
    ddl_sql      String CODEC(ZSTD(3)),
    rationale    String CODEC(ZSTD(3)),
    decision     LowCardinality(String),   -- pending | approved | rejected
    decided_by   LowCardinality(String) DEFAULT ''   -- cli | ui | 'auto (--yes)'
)
ENGINE = MergeTree
ORDER BY (run_id, ts);

CREATE TABLE IF NOT EXISTS insights_log
(
    run_id       String,
    ts           DateTime64(3) DEFAULT now64(3),
    feature_slug String,
    headline     String,
    metric       String,
    confidence   Float32,
    severity     LowCardinality(String),
    context_refs Array(String),
    payload      String CODEC(ZSTD(3))   -- full Finding JSON
)
ENGINE = MergeTree
ORDER BY (ts, run_id);
