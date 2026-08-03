-- =============================================================================
-- 003_events_clean.sql — the derivation layer: normalized, keyed, deduplicable
--
-- Three responsibilities, split across three objects, in the order a row moves
-- through them:
--
--   events_clean            normalized rows, one per landed row, sorted on the
--                           semantic event key
--   events_raw_to_clean_mv  the row-local transform that fills it at insert
--   events_dedup            the deterministic read: exactly one row per
--                           semantic key, resolved by argMax, never FINAL
--
-- Why the dedup lives here and not on events_raw is argued at length in the
-- header of 002_events_raw.sql. The short version: the landing zone is
-- evidence and must not lose rows; this layer is derived and may.
--
-- The engine and the view are BOTH ReplacingMergeTree-shaped, and they are not
-- redundant — they solve two different halves of the same problem:
--
--   the engine  reclaims the space. A re-delivered batch would otherwise add a
--               permanent row that every future read pays to group away. Under
--               an at-least-once producer that cost compounds without bound,
--               and a plain MergeTree has no mechanism to ever reclaim it.
--
--   the view    guarantees the answer. Replacement is eventual: until a merge
--               runs, both copies are visible. A correct read therefore cannot
--               depend on the engine having collapsed anything yet — so
--               events_dedup resolves with argMax and never with FINAL.
--               [official: insert-optimize-avoid-final]
--
-- Neither substitutes for the other. Dropping the engine leaks storage and read
-- time; dropping the view makes the answer a function of merge timing.
--
-- This is also why the same reasoning does NOT extend down to events_raw: there
-- the collapse would destroy evidence rather than reclaim waste. See the header
-- of 002_events_raw.sql.
-- =============================================================================

CREATE TABLE IF NOT EXISTS {{db}}.events_clean
(
    -- ---------------------------------------------------------------------
    -- The semantic event key. These four columns identify an event; two rows
    -- agreeing on all four are the same event, delivered twice.
    --
    -- It is also, exactly, the ORDER BY. Duplicates therefore sort adjacent,
    -- the argMax in events_dedup is a merge over consecutive granule rows
    -- rather than a global hash aggregation, and the RMT flip needs no
    -- reordering.
    -- ---------------------------------------------------------------------
    session_key         UInt64,
    event_ts            DateTime64(3, 'UTC') CODEC(DoubleDelta, ZSTD(1)),
    event_type          LowCardinality(String),
    event               LowCardinality(String),

    -- ---------------------------------------------------------------------
    -- Payload. Carried through so that a touched-session read is served
    -- entirely from this table and never has to go back to the landing zone.
    -- ---------------------------------------------------------------------
    video_session_id    String COMMENT 'Retained for human-readable output; joins use session_key',
    user_key            UInt64,
    user_id             String,
    content_id          Int64,

    session_start_ts    DateTime64(3, 'UTC') CODEC(DoubleDelta, ZSTD(1)),
    session_start_date  Date MATERIALIZED toDate(session_start_ts),
    event_date          Date MATERIALIZED toDate(event_ts),

    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),

    -- ---------------------------------------------------------------------
    -- Normalized dimensions. The raw casing stays in events_raw; these are the
    -- values every downstream GROUP BY must use.
    --
    -- Computed server-side in the MV below rather than in the Go producer, for
    -- one reason: the rule must be identical for every producer forever (CSV
    -- backfill, live generator, a future Kafka consumer). A normalization rule
    -- that lives in one client is a rule that will eventually differ between
    -- clients.
    -- [derived from decision-real-time-preaggregation: transformation that is
    --  row-local and deterministic belongs at the insert boundary]
    -- ---------------------------------------------------------------------
    audio_language      LowCardinality(String) COMMENT 'Normalized: case-folded, suffix-stripped, empty/unk/und -> unknown',
    subtitle_language   LowCardinality(String) COMMENT 'Normalized; "off" is preserved as distinct from "unknown"',
    player_version      LowCardinality(String) COMMENT 'Normalized: trimmed, empty -> unknown',

    -- Normalized resolution. Arrives with the unseen dataset.
    --
    -- ONE rule, whitespace and case: '1920 * 1080' -> '1920*1080'. Measured over
    -- 800,000 surprise rows that collapses 477 raw spellings to 415 and merges
    -- 18.32% + 7.90% = 26.22% of rows into the single bucket they belong in.
    -- Without it a filter on either spelling silently undercounts.
    --
    -- What is deliberately NOT done: the quality-ladder prefix is KEPT.
    -- 'Auto-1280*720' (214,424 rows) is a different playback mode from
    -- '1280*720', not a dirty spelling of it, and collapsing them would destroy
    -- a real distinction to make a column look tidier. 'NA' and 'Auto-Auto' map
    -- to 'unknown' because they name the absence of a resolution.
    video_resolution    LowCardinality(String) COMMENT 'Normalized: spaces removed, case-folded; ladder prefix (Auto-/NA-/DataSaver-) PRESERVED; empty/na/auto -> unknown',

    -- The single most valuable normalization in the whole pipeline: 47
    -- inconsistently-cased event names collapsed into the closed set the
    -- concurrency state machine actually branches on. Pause/resume exist ONLY
    -- as lowercase heartbeat sub-events; a state machine reading event_type
    -- alone cannot see them at all.
    --
    -- Closed set, guaranteed by the trailing 'liveness' fallback in the MV, so
    -- Enum8 is safe here even though event_type upstream is deliberately open.
    -- Adding a class later is a metadata-only ALTER.
    -- [official: schema-types-enum]
    signal Enum8(
        'liveness'      = 1,
        'session_start' = 2,
        'session_end'   = 3,
        'play'          = 4,
        'pause'         = 5,
        'resume'        = 6,
        'background'    = 7,
        'foreground'    = 8,
        'error'         = 9
    ),

    -- The genuinely periodic ping is the {network-activity, buffer-health,
    -- video-resize} trio emitted at one identical millisecond — 53.69% of all
    -- rows. Flagged so the hot path can exclude or TTL it, but NOT used as the
    -- liveness signal: 74.4% of IPHONE sessions never emit the trio, so a
    -- trio-only liveness rule silently drops most iOS traffic.
    is_periodic_ping    Bool,

    -- ---------------------------------------------------------------------
    -- Conflict resolution order.
    --
    -- Exact duplicates agree on every payload column, so for them any winner is
    -- the same winner and this column is decorative. It exists for the other
    -- case: the supplied extract contains one row that shares the semantic key
    -- with another but carries a different payload, and something has to pick,
    -- the same way, every time, on every machine.
    --
    -- The rule is last-write-wins by server receive time, tie-broken by
    -- position within the batch:
    --
    --   row_version = (unix_millis(_ingested_at) << 20) | _batch_row_seq
    --
    -- 20 bits leaves room for 1,048,576 rows per batch against a 100,000-row
    -- recommended ceiling, and the high word stays well inside UInt64 until the
    -- year 557,000. `now64(3)` is evaluated once per inserted block, so within
    -- one batch the pair is unique by construction. Two *different* batches
    -- landing in the same millisecond can collide — but for them to collide on
    -- the same event key they must be carrying the same event, which is the
    -- re-delivery case where either copy is by definition acceptable.
    --
    -- This is also exactly the version column ReplacingMergeTree would need,
    -- which is what makes the engine flip a one-liner.
    -- ---------------------------------------------------------------------
    row_version         UInt64 COMMENT 'Monotonic per row: (ingest millis << 20) | batch row sequence',

    -- Lineage carried forward so a clean row is still traceable to the batch
    -- that produced it without joining back to the landing zone.
    ingest_batch_id     UUID CODEC(ZSTD(1)),

    INDEX idx_event_ts event_ts TYPE minmax GRANULARITY 4,
    INDEX idx_signal   signal   TYPE set(9) GRANULARITY 4
)
-- ReplacingMergeTree(row_version) — storage-level mop-up. See the header for
-- why this does not remove the need for events_dedup.
--
-- Three preconditions make the collapse total rather than partial, and all
-- three are properties of this table specifically:
--
--   * the sort key IS the semantic event key, so duplicates are exactly what
--     the engine considers equal — no more, no less;
--   * PARTITION BY session start, and session start is constant per session,
--     so every copy of an event is guaranteed to be in the same partition.
--     RMT cannot collapse across partitions, and here it never has to;
--   * row_version is monotone and unique per row within a batch, so the
--     survivor of a conflicting-payload pair is the documented one and not an
--     artefact of merge order.
--
-- The row count of this table is consequently NOT deterministic — it depends on
-- which merges have run. That is acceptable precisely because this table is
-- derived: the deterministic count, and the duplicate rate, are measured on
-- events_raw, which never loses a row.
ENGINE = ReplacingMergeTree(row_version)
-- Partition on session start, not event time. session_start_ts is constant per
-- session, so every event of a session — including the 43.6h outlier and any
-- late correction that arrives days later — lands in exactly ONE partition.
-- The touched-session read, the only hot read on this layer, therefore never
-- fans out across partitions, and an RMT flip would never have to collapse
-- duplicates across a partition boundary (it cannot).
-- Daily granularity is for lifecycle; at >2y retention switch to toYYYYMM to
-- stay inside the 100-1,000 partition guidance.
-- [official: schema-partition-lifecycle, schema-partition-low-cardinality]
PARTITION BY toYYYYMMDD(session_start_ts)
-- The semantic event key, in dedup order. See the column block above.
--
-- Leading with a high-cardinality hash is a deliberate exception to
-- "order low-cardinality first" [official rule: schema-pk-cardinality-order],
-- for the same reason it is on events_raw: the only hot read is "give me the
-- complete history of these N touched sessions, in event-time order", which is
-- a point lookup. Dashboard filters (platform / content / time) never touch
-- this table — they are served from the pre-aggregated boundary and minute
-- tables, which order low-cardinality-first as the rule prescribes.
ORDER BY (session_key, event_ts, event_type, event)
SETTINGS
    -- These were MISSING on the live service (measured 2026-08-02), on the
    -- busiest table in the schema, against this repo's own rule that every
    -- MergeTree table must carry all three.
    --
    -- Why it is defence in depth rather than a present wrong answer, stated
    -- precisely so nobody over- or under-reacts: every write to this table
    -- arrives through events_raw_to_clean_mv, and events_raw DOES carry the
    -- settings, so an identical replayed batch is refused upstream and the MV
    -- never fires. On top of that this is a ReplacingMergeTree keyed on the
    -- semantic event key and every read goes through events_dedup's argMax, so
    -- a duplicate that did land would be resolved at read time regardless of
    -- whether a merge had run.
    --
    -- What is NOT covered without these: a replay whose block boundaries differ
    -- from the original passes events_raw's token check (the failure mode that
    -- doubled concurrency_deltas on 2026-08-01), and then lands here. RMT would
    -- still collapse it on key, so the exposure is storage and read cost rather
    -- than correctness — but the whole point of the rule is that the difference
    -- between "silently doubled" and "correctly deduplicated" should not depend
    -- on which of two mechanisms happened to catch it.
    --
    -- Note the interaction already documented in CLAUDE.md: the docs advise
    -- against combining deduplicate_blocks_in_dependent_materialized_views with
    -- async inserts where dependent MVs exist, and the setting that used to make
    -- that pairing throw is obsolete in 26.2, so it now proceeds silently.
    -- ingest/internal/chx/loader.go sets the async path and the MV-dedup path
    -- mutually exclusively for that reason.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Normalized derivation of events_raw. One row per landed row; read through events_dedup.';

-- Converge an existing database: CREATE IF NOT EXISTS cannot deliver settings
-- to a table that already exists, which is why these were absent in production
-- even though the file now declares them.
ALTER TABLE {{db}}.events_clean
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- =============================================================================
-- Normalization MV.
--
-- Strictly row-local: every output column is a function of the one input row.
-- No aggregation, no lead/lag, no lookup against another block. That is what
-- makes it correct under an insert-block-scoped MV, and it is the whole reason
-- the dedup is NOT done here.
--
-- The SELECT reads events_raw's DEFAULT (_ingested_at) and MATERIALIZED
-- (session_key, user_key) columns directly. Verified against ClickHouse
-- 26.5.1.1: the block handed to an MV has already had defaults and materialized
-- expressions applied, so these are populated rather than zero.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS {{db}}.events_raw_to_clean_mv
TO {{db}}.events_clean
AS
SELECT
    session_key,
    event_timestamp     AS event_ts,
    event_type,
    event,

    video_session_id,
    user_key,
    user_id,
    content_id,

    session_start_epoch AS session_start_ts,

    platform,
    app_version,
    country,

    -- Language fields are case-inconsistent by event type. Without this, every
    -- GROUP BY double-counts OFF/off and UNK/unk. 'off' is preserved as a
    -- distinct value: explicitly-disabled subtitles are not the same fact as
    -- unknown subtitles.
    if(lowerUTF8(splitByChar('-', trimBoth(audio_language))[1]) IN ('', 'unk', 'und', 'null', 'unknown'),
       'unknown',
       lowerUTF8(splitByChar('-', trimBoth(audio_language))[1]))       AS audio_language,

    if(lowerUTF8(splitByChar('-', trimBoth(subtitle_language))[1]) IN ('', 'unk', 'und', 'null', 'unknown'),
       'unknown',
       lowerUTF8(splitByChar('-', trimBoth(subtitle_language))[1]))    AS subtitle_language,

    if(empty(trimBoth(player_version)), 'unknown', trimBoth(player_version)) AS player_version,

    -- Whitespace + case only; see the column comment for why the ladder prefix
    -- survives. replaceAll on ' ' rather than trimBoth: the spaces are INSIDE
    -- the value ('1920 * 1080'), not around it, so trimming does nothing.
    if(lowerUTF8(replaceAll(trimBoth(video_resolution), ' ', '')) IN ('', 'na', 'auto', 'auto-auto', 'null', 'unknown'),
       'unknown',
       lowerUTF8(replaceAll(trimBoth(video_resolution), ' ', ''))) AS video_resolution,

    multiIf(
        event_type = 'VideoSessionStart', 'session_start',
        event_type = 'VideoSessionEnd',   'session_end',
        event_type = 'VideoPlay',         'play',
        event_type = 'AppBackgrounded',   'background',
        event_type = 'AppForegrounded',   'foreground',
        event_type = 'VideoError',        'error',
        -- Only the bare 'pause' / 'resume' are play-state transitions.
        --
        -- 'adpause'/'adresume' and 'speed-pause'/'speed-resume' are deliberately
        -- excluded and fall through to 'liveness'. Neither is the viewer
        -- stopping watching:
        --
        --   * an ad break is the player pausing itself — the session is still
        --     open, on screen and being watched;
        --   * a speed-pause/resume pair brackets a playback-rate change, not an
        --     absence.
        --
        -- Classing either as 'pause' would drop the session out of the
        -- concurrency count for the duration of an ad break or a speed change.
        -- For ads that is worst precisely in the hot hours, where ad load is
        -- densest — the metric would sag exactly where it matters most.
        -- 'liveness' is the honest classification: proof the session is alive,
        -- with no play-state transition to apply.
        --
        -- Measured in the supplied extract: speed-pause 380, speed-resume 380,
        -- AdPause 45, AdResume 27 — 832 rows reclassified out of pause/resume.
        -- Small in this extract, but both rates are functions of ad load and
        -- player features rather than of this dataset, so they are not safe to
        -- treat as negligible on the unseen day.
        --
        -- This is a play-state decision only. They are NOT flagged as
        -- is_periodic_ping either — that flag means the {network-activity,
        -- buffer-health, video-resize} trio specifically, and neither an ad nor
        -- a speed change is periodic.
        lowerUTF8(event) = 'pause',  'pause',
        lowerUTF8(event) = 'resume', 'resume',
        'liveness')                                                  AS signal,

    event IN ('network-activity', 'buffer-health', 'video-resize')   AS is_periodic_ping,

    bitShiftLeft(toUInt64(toUnixTimestamp64Milli(_ingested_at)), 20)
        + toUInt64(_batch_row_seq)                                   AS row_version,

    _ingest_batch_id                                                 AS ingest_batch_id
FROM {{db}}.events_raw;


-- =============================================================================
-- The deterministic deduplicated read.
--
-- This is the only object downstream code should read. It returns exactly one
-- row per semantic event key, chosen by the documented conflict order, and it
-- is correct immediately after an insert commits — it does not wait for a
-- merge and it does not use FINAL.
-- [official: insert-optimize-avoid-final]
--
-- Intended access pattern:
--
--     SELECT * FROM events_dedup
--     WHERE session_key IN (SELECT session_key FROM dirty_sessions WHERE ...)
--     ORDER BY event_ts
--
-- session_key is both the leading sort-key column of events_clean and the
-- leading GROUP BY key here, so that predicate is pushed into the aggregation
-- and the read stays a point lookup — p99 434 rows, maximum 1,803 in the
-- supplied extract. An unfiltered SELECT * from this view is a full-table
-- aggregation and is only appropriate for the nightly full-day oracle.
--
-- NOT the place to measure the duplicate rate. events_clean is a
-- ReplacingMergeTree, so how many rows this view collapses depends on which
-- merges have already run — the number shrinks toward zero over time without
-- anything about the data changing. Measure it on the landing zone, which never
-- loses the losing copy:
--
--     SELECT count()                       AS landed,
--            uniqExact(row_fingerprint)    AS distinct_rows,
--            count() - uniqExact(row_fingerprint) AS duplicate_excess
--     FROM (SELECT xxHash64(...) AS row_fingerprint FROM events_raw)
--
-- (the full fingerprint expression is in the header of 002_events_raw.sql, and
-- is what `sonyliv-ingest verify` runs.)
-- =============================================================================

CREATE OR REPLACE VIEW {{db}}.events_dedup AS
SELECT
    session_key,
    event_ts,
    event_type,
    event,

    argMax(video_session_id,   row_version) AS video_session_id,
    argMax(user_key,           row_version) AS user_key,
    argMax(user_id,            row_version) AS user_id,
    argMax(content_id,         row_version) AS content_id,
    argMax(session_start_ts,   row_version) AS session_start_ts,
    argMax(platform,           row_version) AS platform,
    argMax(app_version,        row_version) AS app_version,
    argMax(country,            row_version) AS country,
    argMax(audio_language,     row_version) AS audio_language,
    argMax(subtitle_language,  row_version) AS subtitle_language,
    argMax(player_version,     row_version) AS player_version,
    argMax(video_resolution,   row_version) AS video_resolution,
    argMax(signal,             row_version) AS signal,
    argMax(is_periodic_ping,   row_version) AS is_periodic_ping,
    argMax(ingest_batch_id,    row_version) AS ingest_batch_id,

    -- Not aliased back to `row_version`: an output alias with the same name as
    -- an input column is resolved inside the argMax arguments above and the
    -- view fails to create with ILLEGAL_AGGREGATION.
    max(row_version)                        AS resolved_row_version,

    -- Copies of this key still physically present in events_clean, i.e. that
    -- the background merge has not collapsed yet. A merge-lag observation, NOT
    -- the duplicate rate: it decays to 1 for every key as merges catch up, with
    -- no change to the underlying data. For the duplicate rate, fingerprint
    -- events_raw — see the block above.
    count()                                 AS unmerged_copies
FROM {{db}}.events_clean
GROUP BY session_key, event_ts, event_type, event;
