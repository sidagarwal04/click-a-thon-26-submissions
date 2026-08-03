-- =============================================================================
-- 005_session_intervals.sql — the state boundary
--
-- One row per session holding its complete active-interval list. This is the
-- seam between the two kinds of work in the concurrency model:
--
--   above it   expensive, per-session, ORDER-DEPENDENT   (the state machine)
--   below it   cheap, per-day, ORDER-FREE                (array join + prefix sum)
--
-- Filled by concurrency/sql/010_recompute_sessions.sql, which reads events_dedup.
-- It is NOT filled by a materialized view and cannot be: reconstructing intervals
-- requires seeing a session's events in order, and an incremental MV sees only
-- its own insert block. The dirty-session marking in 003 is block-local for
-- exactly that reason; this layer is where ordering re-enters.
--
-- Why ReplacingMergeTree and not a signed-delta ledger
-- ---------------------------------------------------------------------------
-- A session's interval list is a PURE FUNCTION of its complete event set —
-- independent of arrival order and of anything previously published. So a
-- recompute REPLACES the session's row rather than emitting a correction, and
-- replacement is idempotent for free: rerun it and you get identical intervals
-- under a higher version.
--
-- That removes the entire apparatus an additive SummingMergeTree needs in order
-- to survive a retry — a previous-state table to diff against, a change ledger,
-- a batch ledger, a sealed snapshot, a generation manifest. Every one of those
-- exists to protect additivity, not to produce the answer. Without additivity
-- the whole failure class is gone, along with the tables.
--
-- A session that loses all its active time writes an EMPTY array, and that empty
-- array is the retraction. Nothing has to be deleted.
--
-- Three properties make the collapse total rather than partial:
--
--   * session_start_date derives from the Start event and is therefore constant
--     per session, so a session never migrates between partitions and
--     replacement always resolves inside one partition. ReplacingMergeTree
--     cannot collapse across partitions, and here it never has to. This is also
--     what makes do_not_merge_across_partitions_select_final = 1 safe on reads.
--   * the sort key is exactly the session identity, so "equal" to the engine
--     means "same session" — no more, no less.
--   * version is milliseconds-since-epoch at recompute time, so the survivor is
--     the newest computation and not an artefact of merge order.
--
-- As with events_clean, replacement is EVENTUAL. Readers must resolve with FINAL
-- or argMax and must not assume a merge has run.
-- =============================================================================

CREATE TABLE IF NOT EXISTS {{db}}.session_intervals
(
    session_start_date  Date     COMMENT 'toDate(first VideoSessionStart); stable per session, hence the partition key',
    session_key         UInt64   COMMENT 'sipHash64(video_session_id); the join key everywhere downstream',
    video_session_id    String   COMMENT 'Retained for human-readable output; joins use session_key',

    version             UInt64   COMMENT 'Milliseconds since epoch at recompute time; higher wins',
    policy_version      LowCardinality(String) COMMENT 'Semantic contract the intervals were computed under',

    -- Session-static dimensions, anchored to the first VideoSessionStart.
    -- Anchoring rather than per-event attribution is deliberate: 120 sessions
    -- carry two user_ids and 95 span two platforms, and letting row drift move a
    -- session between slices would change concurrency counts.
    user_key            UInt64,
    canonical_user_id   String,
    content_id          Int64,
    platform            LowCardinality(String),
    country             LowCardinality(String),
    app_version         LowCardinality(String),
    video_type          LowCardinality(String) COMMENT 'Resolved via content_dict at recompute time',

    has_terminal_end    Bool     COMMENT 'A VideoSessionEnd was observed',
    terminal_end_time   DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC')
                                 COMMENT 'FIRST End (policy end_choice: first); 0 when none',

    -- Half-open [start, end) in UTC, sorted by start, guaranteed disjoint by the
    -- island merge in the recompute query. Order is load-bearing: the day rebuild
    -- does not re-sort.
    intervals           Array(Tuple(start_time DateTime64(3, 'UTC'), end_time DateTime64(3, 'UTC'))),

    source_event_count  UInt32   COMMENT 'Deduplicated events the row was computed from',
    computed_at         DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(session_start_date)
ORDER BY (session_start_date, session_key)
COMMENT 'One row per session: its complete active-interval list. Replaced wholesale on recompute; read with FINAL or argMax.';
