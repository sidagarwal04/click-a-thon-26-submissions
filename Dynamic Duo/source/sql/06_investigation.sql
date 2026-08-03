-- Investigation output: the handoff surface between detection and the RCA agent,
-- and the queryable trace judges can replay.
--
-- incidents            detection writes (sweep chronological / alert webhook);
--                      agent updates status. Deterministic incident_id
--                      ({window}_{metric}_{scope}) makes both sources idempotent.
--                      Baseline rule 3's excluded-dates list is a SELECT over this
--                      table's past verdicts.
-- investigation_steps  one row per agent step: hypothesis, EXACT sql, result, decision.
--                      "What was checked, in what order, and why" = ORDER BY step_no.
-- diagnoses            final narrative + evidence bundle + guardrail verdict.

CREATE TABLE IF NOT EXISTS rca.incidents
(
    incident_id  String,
    run_id       String,
    source       Enum8('sweep' = 1, 'alert' = 2),
    metric       LowCardinality(String),
    scope        String,                         -- 'global' | 'region=NAM' | 'os_version=Android 15' ...
    window_start DateTime('UTC'),
    window_end   DateTime('UTC'),
    z_score      Float64,
    pct_change   Float64,
    status       Enum8('detected' = 1, 'investigating' = 2, 'diagnosed' = 3,
                       'ruled_out_seasonal' = 4, 'dismissed' = 5),
    updated_at   DateTime('UTC') DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY incident_id;

CREATE TABLE IF NOT EXISTS rca.investigation_steps
(
    incident_id String,
    step_no     UInt16,
    ts          DateTime64(3, 'UTC') DEFAULT now64(3),
    step_type   Enum8('detect' = 1, 'decompose' = 2, 'dim_scan' = 3, 'drill_down' = 4,
                      'rule_out' = 5, 'mix_check' = 6, 'peer_check' = 7,
                      'narrate' = 8, 'verify' = 9),
    hypothesis  String,      -- what this step tested, plain language
    sql_text    String,      -- the exact query that ran (reproducible verbatim)
    result      String,      -- JSON rows returned
    decision    String,      -- conclusion + why the next step follows
    duration_ms UInt32
)
ENGINE = MergeTree
ORDER BY (incident_id, step_no);

CREATE TABLE IF NOT EXISTS rca.diagnoses
(
    incident_id      String,
    version          UInt8,
    created_at       DateTime('UTC') DEFAULT now(),
    headline         String,
    narrative        String,
    evidence         String,            -- JSON bundle: every number the narrative may cite
    ruled_out        Array(String),
    verdict_code     LowCardinality(String),  -- PEER_OUTLIER / CAUSE_CONFIRMED / GLOBAL_MOVEMENT / …
    llm_model        LowCardinality(String),
    numbers_verified Bool,              -- guardrail: every figure in narrative ∈ evidence
    trace_id         String             -- OTel trace for this investigation
)
ENGINE = ReplacingMergeTree(version)
ORDER BY incident_id;

-- migration for tables created before verdict_code existed (CREATE IF NOT EXISTS
-- never alters): idempotent, no-op on fresh databases
ALTER TABLE rca.diagnoses ADD COLUMN IF NOT EXISTS verdict_code LowCardinality(String) DEFAULT '' AFTER ruled_out;
