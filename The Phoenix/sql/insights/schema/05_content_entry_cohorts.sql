-- INSIGHTS: retention by entry cohort. "Did the audience that arrived at 10:56 stay?"
--
-- A cohort is the set of sessions whose FIRST ACTIVE MINUTE is the same minute, for the same
-- dimension tuple. Cohorting on first_active_at and not on session_start is the plan's Phase 5
-- rule and it matters: a session that opens at 10:50 and does not reach the foreground until
-- 10:56 belongs to the 10:56 audience, which is the audience a spike is asking about.
--
-- RETENTION IS EVALUATED AT AN INSTANT, NOT AS "HAS NOT ENDED". retention_5m counts sessions
-- that were in a foreground interval at first_active_at + 5 minutes. A session backgrounded at
-- minute 5 is NOT retained at minute 5, even though it has not ended and will come back. The
-- plan's Phase 5 gate names that trap specifically, and the flags this table sums were built to
-- answer it that way in session_insight_facts, where they are validated against a second engine.

CREATE TABLE IF NOT EXISTS content_entry_cohorts
(
    cohort_minute DateTime,
    content_id    Int64,
    title         String,
    category      LowCardinality(String),
    video_type    LowCardinality(String),
    platform      LowCardinality(String),
    country       LowCardinality(String),
    app_version   LowCardinality(String),

    entered_sessions UInt32,
    active_after_1m  UInt32,
    active_after_5m  UInt32,
    active_after_10m UInt32,
    active_after_15m UInt32,

    retention_1m  Float32,
    retention_5m  Float32,
    retention_10m Float32,
    retention_15m Float32,

    avg_active_seconds    Float32,
    median_active_seconds Float32,
    p90_active_seconds    Float32,

    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMMDD(cohort_minute)
-- RE-KEYED, and this one also fixes a correctness hazard. The old key was (content_id,
-- cohort_minute, platform, country, app_version), which omitted video_type. This is a
-- ReplacingMergeTree, so ORDER BY IS the dedup key, and the refresh writes at a grain that
-- INCLUDES video_type: two cohorts differing only by video_type shared a key and one would have
-- been discarded. Measured 0 collisions today, because video_type is functionally determined by
-- content_id with 0 exceptions, but that invariant is undeclared and unchecked.
--
-- Cardinality now ascends: video_type 3, country 5, platform 15, app_version 66, content_id
-- 3,366, then cohort_minute. Time comes last here, unlike session_insight_facts, because this
-- table is partitioned by DAY, so a day-window query has already pruned before the key is
-- consulted. Same reasoning as concurrency_deltas.
PRIMARY KEY (video_type, country, platform, app_version)
ORDER BY (video_type, country, platform, app_version, content_id, cohort_minute);

-- active_after_30m and retention_30m are in the plan and not here. session_insight_facts carries
-- flags at 1, 5, 10 and 15 minutes only, and those four are the ones validated against the
-- independent ground truth. Adding a 30-minute column would mean adding it to the facts table
-- and to both sides of that comparison, which is a change to a validated table for a column
-- nothing currently asks for. Add it there first, then here.

-- TTL, written and NOT active. See docs/RETENTION.md.
-- TTL cohort_minute + INTERVAL 24 MONTH WHERE toDate(cohort_minute) >= toDate('2026-08-01')
