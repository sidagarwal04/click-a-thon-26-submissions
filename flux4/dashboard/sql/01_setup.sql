
-- 1. Plain-English cache. One row per distinct rationale string, so the LLM is
--    called once per new phrasing and never again. Keeps the demo instant.
CREATE TABLE IF NOT EXISTS rca.rationale_cache
(
    rationale_hash UInt64,
    rationale      String,
    plain_text     String,
    model          LowCardinality(String),
    created_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY rationale_hash;

-- 2. App telemetry. Every endpoint call lands here, success or failure.
--    This is what the success/failure panel reads -- the dashboard observes
--    itself using the same warehouse it serves from.
CREATE TABLE IF NOT EXISTS rca.app_events
(
    event_id      UUID DEFAULT generateUUIDv4(),
    ts            DateTime64(3) DEFAULT now64(3),
    endpoint      LowCardinality(String),
    run_id        String,
    status        LowCardinality(String),   -- success | failure
    stage         LowCardinality(String),   -- clickhouse | llm | cache_hit
    latency_ms    UInt32,
    rows_returned UInt32,
    error         String,
    trace_id      String                    -- joins straight to Langfuse
)
ENGINE = MergeTree
ORDER BY (ts, endpoint)
TTL toDateTime(ts) + INTERVAL 30 DAY;
ORDER BY (run_id, step_number);

-- Sanity check after your loader runs:
-- SELECT run_id, count(), max(created_at) FROM rca.audit_log GROUP BY run_id ORDER BY 3 DESC;
