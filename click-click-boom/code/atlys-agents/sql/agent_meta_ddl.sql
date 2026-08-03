-- Agent metadata layer: schema proposals, reviews, tests, insights, context versions.
-- Separate database from `atlys` (the event data) — this is our own workflow state.

CREATE DATABASE IF NOT EXISTS agent_meta;

CREATE TABLE IF NOT EXISTS agent_meta.schema_proposals
(
    proposal_id UUID,
    parent_proposal_id Nullable(UUID),
    revision UInt8 DEFAULT 0,
    ts DateTime DEFAULT now(),
    spec_name String,
    table_name String,
    ddl String,
    ordering_key String,
    partition_key String,
    materialized_views Array(String),
    perf_report String,
    confidence Float32,
    rationale String,
    status Enum8(
        'drafted'=1,
        'pending_review'=2,
        'needs_rework'=3,
        'approved'=4,
        'executed'=5,
        'rejected'=6
    ),
    trace_url String
)
ENGINE = MergeTree
ORDER BY (spec_name, ts);

CREATE TABLE IF NOT EXISTS agent_meta.schema_reviews
(
    review_id UUID,
    ts DateTime DEFAULT now(),
    proposal_id UUID,
    revision UInt8,
    verdict Enum8('approve'=1,'request_changes'=2,'block'=3),
    findings String,
    context_sections_used Array(String),
    reviewer_confidence Float32,
    trace_url String
)
ENGINE = MergeTree
ORDER BY (proposal_id, ts);

CREATE TABLE IF NOT EXISTS agent_meta.test_cases
(
    test_id UUID,
    ts DateTime DEFAULT now(),
    introduced_by_proposal_id UUID,
    table_name String,
    test_type Enum8('schema'=1,'insert_integrity'=2,'query_smoke'=3,'mv_integrity'=4),
    query String,
    expected String,
    description String
)
ENGINE = MergeTree
ORDER BY (table_name, ts);

CREATE TABLE IF NOT EXISTS agent_meta.test_runs
(
    run_id UUID,
    ts DateTime DEFAULT now(),
    proposal_id UUID,
    test_id UUID,
    passed UInt8,
    actual String,
    duration_ms UInt32,
    trace_url String
)
ENGINE = MergeTree
ORDER BY (proposal_id, ts);

CREATE TABLE IF NOT EXISTS agent_meta.insights
(
    insight_id UUID,
    ts DateTime DEFAULT now(),
    spec_name String,               -- '' for a custom/broad-prompt investigation (see `prompt` below)
    title String,
    summary String,
    segment_cuts Array(String),
    evidence String,
    related_known_issues Array(String),
    confidence Float32,
    trace_url String,
    report_html String DEFAULT '',  -- self-contained HTML insight report (see analytics/analytics_agent.py)
    prompt String DEFAULT ''        -- the user's free-text question, for a custom_investigation-triggered insight only
)
ENGINE = MergeTree
ORDER BY (spec_name, ts);

-- The spec's own spec.md, captured at ingest time. Nothing else durably
-- stores this today -- ingest_spec() only ever received it as an in-memory
-- argument. Needed so the analytics agent can be triggered as an explicit,
-- LATER step (from the dashboard's "Create Insight" button) against a spec
-- that finished ingesting in some earlier process -- without it, there's no
-- way to hand the analytics agent the spec_markdown it needs. Append-only
-- like every other agent_meta table; argMax(spec_markdown, ts) gets the
-- latest if a spec is ever re-ingested.
CREATE TABLE IF NOT EXISTS agent_meta.spec_sources
(
    ts DateTime DEFAULT now(),
    spec_name String,
    spec_markdown String
)
ENGINE = MergeTree
ORDER BY (spec_name, ts);

CREATE TABLE IF NOT EXISTS agent_meta.context_versions
(
    version_id UUID,
    ts DateTime DEFAULT now(),
    section String,
    before String,
    after String,
    diff_summary String,
    rationale String,
    trigger String,
    confidence Float32,
    trace_url String
)
ENGINE = MergeTree
ORDER BY (section, ts);

-- Every reasoning/tool_call/generation/span/trace event from a pipeline run,
-- durably stored (previously only lived in Langfuse + the ephemeral 8787/SSE
-- live streams -- nothing survived after a run ended). Written as ONE bulk
-- INSERT per trace at traced_run()'s end (tracing/langfuse_wrapper.py), not
-- per-event, to avoid many small inserts against a run that can emit dozens
-- of events. DateTime64(3): events from the same tool-calling turn can land
-- within the same second, and second-precision ordering isn't enough to
-- replay them correctly.
CREATE TABLE IF NOT EXISTS agent_meta.trace_events
(
    event_id UUID DEFAULT generateUUIDv4(),
    ts DateTime64(3),
    trace_id String,
    trace_url String,
    agent String,
    spec_name String,
    step String,
    event String,   -- raw sub-type as emitted: log / span_start / span_end / trace_start / trace_end
    kind String,    -- tool_call / reasoning / generation / span / trace / log
    input String,
    output String,
    reasoning String,
    usage String,     -- JSON-encoded {input, output, total, reasoning}
    metadata String   -- JSON-encoded (model_reasoning, n_tool_calls, revision, ...)
)
ENGINE = MergeTree
ORDER BY (spec_name, trace_id, ts);
