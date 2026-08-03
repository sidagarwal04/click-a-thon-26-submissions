-- =============================================================================
-- 002_events_raw.sql — the landing zone: exactly as received, never rewritten
--
-- This table is the evidence layer. Its contract is narrow and absolute:
--
--   * every accepted source row lands here verbatim;
--   * nothing is corrected, coalesced, normalized, collapsed or dropped;
--   * no row is ever mutated or replaced — corrections arrive as new rows.
--
-- That contract is why the engine is a plain MergeTree and NOT a
-- ReplacingMergeTree keyed on the semantic event key, which is the obvious
-- alternative for a stream with a known 0.465% exact-duplicate rate. Three
-- reasons, in order of weight:
--
--   1. RMT replacement is eventual. Until a background merge runs, both copies
--      are visible to every SELECT, so a correct read still needs argMax or
--      FINAL. The dedup logic does not go away; it just gains a second,
--      non-deterministic mechanism next to it. An answer must not depend on
--      whether a merge happened to fire before the query did.
--
--   2. It destroys the audit property. "The extract contains 4,209 excess exact
--      rows and one conflicting-payload row, here they are, here is how they
--      were resolved" is the evidence. Under RMT the row count of this table
--      drifts as merges run, and the losing copy of a conflicting pair is gone
--      — so the duplicate rate stops being measurable and a weird session stops
--      being re-derivable.
--
--   3. There is no valid single version column. Resolution needs
--      (_ingested_at, _ingest_batch_id, _batch_row_seq) as an ordered tuple;
--      RMT takes one column, and every single existing column gets the
--      conflicting-payload case wrong on its own.
--
-- Duplicates are handled in two places instead, each where it is cheap:
--   * retried or replayed INSERT batches      -> insert_deduplication_token
--                                                plus the windows set below;
--   * row-level duplicates within the stream  -> deterministically, one layer
--                                                up, in 003_events_clean.sql.
-- =============================================================================

CREATE TABLE IF NOT EXISTS {{db}}.events_raw
(
    -- ---------------------------------------------------------------------
    -- Source-faithful payload. Column names match the source CSV header, not
    -- the downstream model, so that reading this table next to the file needs
    -- no mental mapping. Renaming to the analytical vocabulary
    -- (event_timestamp -> event_ts, session_start_epoch -> session_start_ts)
    -- happens exactly once, at the boundary into events_clean.
    -- ---------------------------------------------------------------------

    -- Int64, not UInt32.
    --
    -- The catalogue's domain is signed: it contains -987654322, written by the
    -- source system as the unsigned 18446744072721897294, and
    -- csvsrc.ParseContentID recovers it as a negative Int64. An unsigned column
    -- would reject that row outright at insert. The largest positive id
    -- observed is 2,078,177,474 — inside UInt32, but only 96.8% of Int32 max,
    -- so the headroom argument does not survive the unseen day either.
    -- The extra bytes compress away; a rejected row does not.
    content_id          Int64 COMMENT 'Signed: catalogue contains a negative id stored unsigned',

    -- String, not FixedString(64). This is a landing table: the source
    -- guarantees 64-char uppercase hex today, and a String keeps a row that
    -- violates that guarantee tomorrow landable and inspectable rather than
    -- turning it into an insert-time error. The fixed-width win is taken one
    -- layer up, where the ids are already validated — events_clean sorts on
    -- session_key (UInt64), not on the hex string at all.
    video_session_id    String COMMENT '64-char uppercase hex, kept verbatim',
    user_id             String COMMENT '64-char uppercase hex, kept verbatim',

    -- Left open (LowCardinality(String), not Enum) on purpose: the dictionary
    -- lists 7 event types but the unseen day may introduce more, and an Enum
    -- would reject the entire insert block rather than land the row. The
    -- closed, validated classification lives in events_clean.signal.
    event_type          LowCardinality(String),
    event               LowCardinality(String) COMMENT '47 distinct values; 41 hide under event_type=VideoHeartbeat',

    -- DoubleDelta: event_timestamp is the second ORDER BY column, so within
    -- each session it is stored ascending and second differences are tiny.
    event_timestamp     DateTime64(3, 'UTC') COMMENT 'From Unix epoch millis. The only time axis concurrency is computed on.' CODEC(DoubleDelta, ZSTD(1)),

    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),

    -- Raw casing preserved here, deliberately. VideoSessionStart emits
    -- lowercase 'unk'/'' while later events emit 'UNK'/'OFF'/'ENG', and some
    -- carry an 'eng-English' suffix form. Collapsing that here would delete the
    -- evidence that the source is inconsistent; it is collapsed in
    -- events_clean, where the rule is stated once and applies to every
    -- producer.
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),

    -- Arrives with the unseen dataset (data/surprise_spec.md). Raw spelling
    -- preserved, like the language columns above and for the same reason: the
    -- source is inconsistent and that inconsistency is evidence.
    --
    -- Measured over an 800,000-row sample of the surprise extract: 477 distinct
    -- raw values, and the inconsistency is not cosmetic --
    --   '1920*1080'      18.32%
    --   '1920 * 1080'     7.90%   <- same resolution, spaces around the star
    -- so a dashboard filtering one spelling silently misses a quarter of the
    -- matching rows. Normalisation happens once, in events_clean.
    --
    -- Quality-ladder prefixes are real and are NOT stripped: Auto (214,424),
    -- NA (11,228), DataSaver (6,310), Advanced (3,619). 'Auto-1280*720' is a
    -- different playback mode from '1280*720', not a dirty spelling of it.
    --
    -- DEFAULT '' so the 13-column original extract still loads: the column is
    -- legitimately absent there rather than missing.
    video_resolution    LowCardinality(String) DEFAULT '' COMMENT 'Raw spelling; 477 distinct in the surprise extract. Normalized in events_clean',

    session_start_epoch DateTime64(3, 'UTC') COMMENT 'From Unix epoch millis; constant per session in the extract' CODEC(DoubleDelta, ZSTD(1)),

    -- ---------------------------------------------------------------------
    -- Derived keys. Additive, never replacing the source value: the hex id
    -- stays right there in the column next to it.
    --
    -- These are the join/sort currency of every downstream layer. 64-bit
    -- integers sort, group and hash-join at a fraction of the cost of a
    -- 64-character string, and they are stable — sipHash64 is not seeded per
    -- process, so the same id yields the same key on every server, forever.
    -- ---------------------------------------------------------------------
    session_key         UInt64 MATERIALIZED sipHash64(video_session_id),
    user_key            UInt64 MATERIALIZED sipHash64(user_id),

    -- ---------------------------------------------------------------------
    -- Ingest lineage, underscore-prefixed to keep it visually separate from
    -- the source payload. Present so that "which pipeline run produced this
    -- row" is answerable from the data itself — the problem statement scores
    -- pipeline evidence, and an unattributable row is not evidence.
    -- ---------------------------------------------------------------------

    -- Server receive time, at millisecond precision rather than DateTime's
    -- second: real lateness is _ingested_at - event_timestamp, the stream's
    -- inter-event cadence is ~40s, and a one-second quantum is coarse enough
    -- to distort the tail of that distribution. It is also the high word of
    -- events_clean.row_version, which needs to order rows inside one second.
    _ingested_at        DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(DoubleDelta, ZSTD(1)),

    _source_file        LowCardinality(String) DEFAULT '' COMMENT 'e.g. ch-hackathon-raw-data.csv | generator',

    -- Batch address. Deterministic per (source, fingerprint, batch ordinal), so
    -- a replay reproduces the same id rather than minting a new one. Two things
    -- depend on this pair existing:
    --   * dirty_sessions.dirty_operation_id, the identity of a queue item, so
    --     that "has this work been applied?" is a set membership test;
    --   * the join to ingest_batches, which is how a row is traced back to the
    --     INSERT that carried it.
    _ingest_batch_id    UUID DEFAULT toUUID('00000000-0000-0000-0000-000000000000') CODEC(ZSTD(1)),

    -- Row position inside the batch. Rows are stored in ORDER BY sequence, not
    -- arrival sequence, so this column is scrambled on disk and does not
    -- delta-compress. T64 transposes the bit planes — the values only occupy
    -- ~17 of 32 bits — which recovers most of the loss regardless of order.
    _batch_row_seq      UInt32 DEFAULT 0 CODEC(T64, ZSTD(1)),

    -- NOTE: there is deliberately no stored row-fingerprint column here.
    --
    -- A 64-bit hash of the row is, by construction, incompressible: measured at
    -- 1x it was 6.16 MiB of a 17.34 MiB table — 35% of on-disk size at a
    -- compression ratio of 1.0 — for a column no hot-path query reads. Exact
    -- duplicates already sort adjacently under the ORDER BY below, and the
    -- touched-session read is a few hundred rows, so the fingerprint is cheaper
    -- to compute on demand than to store. Computing it server-side also removes
    -- the risk of a client and the server disagreeing on the canonical form.
    --
    -- The canonical fingerprint, used by `sonyliv-ingest verify`:
    --
    --   xxHash64(concatWithSeparator('\x1F',
    --       video_session_id, user_id, toString(content_id),
    --       event_type, event, toString(toUnixTimestamp64Milli(event_timestamp)),
    --       platform, app_version, country,
    --       audio_language, subtitle_language, player_version,
    --       toString(toUnixTimestamp64Milli(session_start_epoch))))

    -- The sort key leads with video_session_id, so a time-ranged scan of the
    -- landing table has no primary-index support. A session's events are
    -- tightly time-clustered (p50 span ~12 min), so the per-granule min/max of
    -- event_timestamp is narrow and prunes well.
    -- [official: query-index-skipping-indices]
    INDEX idx_event_timestamp event_timestamp TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree
-- Monthly partitions on event time. Coarse on purpose: partitions here are for
-- lifecycle (DROP PARTITION / TTL of the landing zone), not for query pruning —
-- no hot query reads this table. Monthly keeps the count inside the 100-1,000
-- guidance for any realistic retention, and it is coarse enough that the 43.6h
-- session outlier stays inside one partition except at a month boundary.
-- The stricter "one session, exactly one partition" property is enforced where
-- it actually matters, on events_clean, which partitions by session start.
-- [official: schema-partition-lifecycle, schema-partition-low-cardinality]
PARTITION BY toYYYYMMDD(event_timestamp)
-- Deliberate exception to "order low-cardinality first".
-- [official rule: schema-pk-cardinality-order — overridden here, with cause]
--
-- Nothing queries this table by dimension. It is written once, read for replay
-- and for audit ("show me every row of session X as it arrived"), and drained
-- by the MVs below. A session-leading key turns the replay read into a handful
-- of granules; putting platform or a date first would serve no query at all.
--
-- Secondary benefit: the source file is already session-major, so this ordering
-- also gives near-optimal compression on the ingest path — the two 64-char hex
-- id columns compress ~58x because equal values are adjacent, and byte-
-- identical duplicate rows land in consecutive positions, which makes counting
-- them a local scan rather than a global hash aggregation.
ORDER BY (video_session_id, event_timestamp)
SETTINGS
    -- Idempotency, stated once and enforced on both engine families.
    --
    -- This is the duplicate mechanism that actually pays for itself: it kills
    -- the retried-identical-batch case outright, before the rows are written,
    -- at zero read cost. It is orthogonal to row-level duplicates in the
    -- source, which are resolved in 003_events_clean.sql.
    --
    -- Which of these applies is decided by the engine, not by this file. A
    -- local MergeTree honours the non_replicated_* window and ignores the rest;
    -- a Replicated or SharedMergeTree (what ClickHouse Cloud silently creates
    -- from `ENGINE = MergeTree`) does the opposite. Setting only the first is
    -- the trap: it works perfectly on a laptop and quietly stops working in
    -- production.
    --
    -- 1000 blocks x 50K rows = 50M rows of retry protection on either engine.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    -- The server default here is 3600 — one hour. There is no time component at
    -- all on the non-replicated path, so "re-running a load is a no-op" is true
    -- indefinitely on a laptop and expires overnight on Cloud. 30 days makes the
    -- guarantee mean the same thing in both places.
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Landing zone: source rows exactly as received. Append-only, never mutated, never deduplicated in place.';

-- CREATE TABLE IF NOT EXISTS above is a no-op against a database that already
-- has this table, so the settings correction would never reach one. This makes
-- `schema` converge rather than merely not-fail: it is metadata-only, costs
-- nothing, and re-running it changes nothing.
ALTER TABLE {{db}}.events_raw
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;

-- Additive column, for the same convergence reason: CREATE TABLE IF NOT EXISTS
-- cannot deliver a new column to a database that already has the table. Adding
-- a column with a DEFAULT is metadata-only -- existing parts are not rewritten,
-- and the default is materialised on read until they are merged.
--
-- NOTE: the PARTITION BY above changed from toYYYYMM to toYYYYMMDD on
-- 2026-08-02. PARTITION BY is IMMUTABLE, so unlike this column that change
-- reaches a NEW table only. An existing events_raw keeps monthly partitions and
-- there is no ALTER that fixes it -- it needs a rebuild. That was free here
-- because the database was being recreated anyway.
ALTER TABLE {{db}}.events_raw
    ADD COLUMN IF NOT EXISTS video_resolution LowCardinality(String) DEFAULT ''
        COMMENT 'Raw spelling; 477 distinct in the surprise extract. Normalized in events_clean'
        AFTER player_version;


-- =============================================================================
-- Touched-session queue
--
-- An incremental materialized view is used here and in the normalization MV in
-- 003, and nowhere else, because these are the only two derivations that are
-- correct block-locally: "which sessions appear in the block I just inserted"
-- and "what does this row say, normalized". Neither ever needs to see another
-- block.
--
-- What an incremental MV must NOT be asked to do on this stream — and the
-- reason the concurrency model is not an MV over events:
--   * lead/lag across events (the next event may be in another block)
--   * "was this session foregrounded before?" (prior state is in another block)
--   * retract previously emitted output (an MV only appends)
--   * deduplicate (the other copy may be in another block — which is exactly
--     why dedup in 003 is a read-time resolution, not an MV)
-- 99.65% of sessions contain at least one out-of-order event, so any of the
-- above would be wrong for nearly every session.
-- [official: query-mv-incremental — incremental MVs are insert-block scoped]
-- =============================================================================

CREATE TABLE IF NOT EXISTS {{db}}.dirty_sessions
(
    session_key          UInt64,
    video_session_id     String,
    session_start_date   Date,
    ingest_batch_id      UUID,
    max_batch_row_seq    UInt32,
    last_ingested_at     DateTime64(3, 'UTC'),
    event_count          UInt32,
    min_event_time       DateTime64(3, 'UTC'),
    max_event_time       DateTime64(3, 'UTC'),

    -- Deterministic identity for the work item. A replayed insert produces the
    -- same id, so the downstream "has this been applied?" check is a set
    -- membership test rather than a guess.
    dirty_operation_id   UInt64 MATERIALIZED
        xxHash64(concatWithSeparator('\x1F',
            toString(session_key), toString(ingest_batch_id), toString(max_batch_row_seq)))
)
ENGINE = MergeTree
ORDER BY (session_start_date, session_key, last_ingested_at, ingest_batch_id)
SETTINGS
    -- These were MISSING. Measured on the live service 2026-08-02: of the 13
    -- MergeTree tables in `sonyliv`, four carried none of the three dedup
    -- settings — dirty_sessions, events_clean, ingest_batches, ingest_rejects —
    -- against this repo's own stated rule that "every new MergeTree table in
    -- this project must carry all three settings".
    --
    -- Scoped honestly, because the blast radius differs per table. This one is
    -- fed by events_raw_to_dirty_mv, and events_raw DOES carry the settings, so
    -- a byte-identical replayed batch is rejected upstream and the MV never
    -- fires. The exposure is a replay whose BLOCK BOUNDARIES differ from the
    -- original — which is precisely the case
    -- insert_deduplication_token does not cover on a large INSERT SELECT, and
    -- the case that doubled concurrency_deltas on 2026-08-01. Then the queue
    -- gains duplicate work items.
    --
    -- Duplicated queue items are tolerated BY DESIGN downstream —
    -- dirty_operation_id makes "has this been applied?" a set-membership test,
    -- and 011 resolves by state_revision — so this is defence in depth, not a
    -- present wrong answer. It is still the rule, and the rule exists because
    -- the failure is silent.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Append-only work queue: sessions whose history changed and must be recompacted.';

-- Converge a database that already has the table; CREATE IF NOT EXISTS above
-- cannot deliver the settings to one, which is exactly why they were absent on
-- the live service despite being in this file's sibling tables.
ALTER TABLE {{db}}.dirty_sessions
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;

CREATE MATERIALIZED VIEW IF NOT EXISTS {{db}}.events_raw_to_dirty_mv
TO {{db}}.dirty_sessions
AS
SELECT
    session_key,
    any(video_session_id)       AS video_session_id,
    toDate(session_start_epoch) AS session_start_date,
    _ingest_batch_id            AS ingest_batch_id,
    max(_batch_row_seq)         AS max_batch_row_seq,
    max(_ingested_at)           AS last_ingested_at,
    count()                     AS event_count,
    min(event_timestamp)        AS min_event_time,
    max(event_timestamp)        AS max_event_time
FROM {{db}}.events_raw
GROUP BY session_key, session_start_date, ingest_batch_id;
