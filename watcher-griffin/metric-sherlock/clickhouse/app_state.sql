-- Application-state tables (distinct from the ad_events star schema): persisted
-- investigation history, scan-loop event feed, and follow-up chat turns.
-- These make the UI's history/detail/monitor views real rather than
-- request-scoped -- an investigation run here is retrievable by id later,
-- and every scan tick (anomalous or not) is recorded so "list all the
-- events" has real data behind it, not a fabricated feed.

CREATE TABLE IF NOT EXISTS investigations
(
    id                    UUID,
    created_at            DateTime DEFAULT now(),
    triggered_by          LowCardinality(String),   -- 'manual' | 'scanner'
    metric                LowCardinality(String),
    window_start          DateTime,
    window_end            DateTime,
    current_value         Float64,
    baseline_mean         Float64,
    baseline_sample_count UInt32,
    zscore                Float64,
    is_anomalous          UInt8,
    insufficient_baseline UInt8,
    primary_factor        LowCardinality(String),
    narration             String,
    narration_available   UInt8,
    narration_provider    LowCardinality(String),
    narration_error       String,
    langfuse_trace_url    String,
    evidence_json         String                     -- full EvidenceBundle, incl. the verbatim query trace
)
ENGINE = MergeTree
ORDER BY created_at;

CREATE TABLE IF NOT EXISTS scan_ticks
(
    id               UUID,
    ts               DateTime DEFAULT now(),
    metric           LowCardinality(String),
    window_start     DateTime,
    window_end       DateTime,
    current_value    Float64,
    baseline_mean    Float64,
    zscore           Float64,
    is_anomalous     UInt8,
    investigation_id Nullable(UUID)                  -- set only when the tick triggered a full investigation
)
ENGINE = MergeTree
ORDER BY ts;

CREATE TABLE IF NOT EXISTS investigation_chat
(
    investigation_id UUID,
    turn_index       UInt32,
    role             LowCardinality(String),          -- 'user' | 'assistant'
    content          String,
    created_at       DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (investigation_id, turn_index);
