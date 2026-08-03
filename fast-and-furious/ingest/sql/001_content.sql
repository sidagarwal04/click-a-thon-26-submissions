-- =============================================================================
-- 001_content.sql — content dimension + enrichment dictionary
--
-- Object names are unprefixed (`content_dim`, not `sl_content_dim`), so this
-- schema expects a dedicated database. Set CLICKHOUSE_DATABASE=sonyliv (or
-- similar) rather than loading into `default`, where `events_raw` would be an
-- inviting name to collide with.
-- All timestamps are UTC and millisecond-precise.
-- =============================================================================

-- Content dimension.
--
-- ReplacingMergeTree(source_version) rather than plain MergeTree: the content
-- catalogue is a slowly-changing dimension and a re-load of the same CSV must
-- converge to one row per content_id instead of doubling the table.
-- [official: insert-mutation-avoid-update — replacement semantics with a
--  version column, never ALTER UPDATE]
--
-- This is the one place in the schema where RMT is unambiguously right: a
-- mutable dimension with a natural monotonic version and no audit requirement.
-- `events_raw` is the opposite on all three counts and stays a plain MergeTree;
-- see the header of 002_events_raw.sql.
--
-- content_id is Int64, not Int32:
--   * the supplied catalogue contains 18446744072721897294, which is
--     -987654322 stored as an unsigned 64-bit value, so the domain is signed;
--   * the largest positive id observed is 2,078,177,474 = 96.8% of Int32 max.
-- Int32 would fit today's extract but leaves ~3.2% headroom before an overflow
-- silently corrupts the join key on the unseen day. The extra 4 bytes on a
-- 33K-row dimension is free, and on the event table it compresses away.
-- [derived: schema-types-minimize-bitwidth says smallest type that FITS —
--  the range that must fit is the source domain, not one sample of it]
CREATE TABLE IF NOT EXISTS {{db}}.content_dim
(
    content_id      Int64,
    title           String,
    video_type      LowCardinality(String) DEFAULT 'unknown',
    category        LowCardinality(String) DEFAULT 'unknown',

    -- Arrives with the unseen dataset (data/surprise_spec.md), "used as a filter
    -- dimension". Measured on the surprise catalogue: 33,326 rows, 360 distinct
    -- show names, ZERO empty -- so LowCardinality is right and comfortable.
    --
    -- DEFAULT '' and NOT 'unknown', unlike video_type and category above. Those
    -- two have a documented empty-means-unclassified case in the source; there is
    -- no such evidence for show_name, and mapping absent to 'unknown' would make
    -- "this catalogue has no show names at all" -- which is exactly the original
    -- 4-column extract -- indistinguishable from "this title has none".
    show_name       LowCardinality(String) DEFAULT '',

    source_version  UInt64 COMMENT 'Monotonic load version; highest wins',
    loaded_at       DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(source_version)
ORDER BY content_id
SETTINGS
    -- Without this, insert_deduplication_token is ignored on a non-replicated
    -- MergeTree and re-running the loader appends a second full copy of the
    -- catalogue. ReplacingMergeTree would eventually collapse it, but "wait for
    -- a merge" is not a substitute for not writing the rows.
    --
    -- The replicated_* pair is the same guarantee for a Replicated or
    -- SharedMergeTree, which is what ClickHouse Cloud creates from this DDL.
    -- Only the engine decides which pair is read; see events_raw for why
    -- setting just the first one is a trap.
    non_replicated_deduplication_window = 100,
    replicated_deduplication_window = 100,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Content catalogue. 33,464 rows in the supplied extract, content_id unique.';

-- Converge a database that already has the table; see events_raw.
ALTER TABLE {{db}}.content_dim
    MODIFY SETTING
        non_replicated_deduplication_window = 100,
        replicated_deduplication_window = 100,
        replicated_deduplication_window_seconds = 2592000;

-- Additive; CREATE TABLE IF NOT EXISTS cannot deliver a column to an existing
-- table. Metadata-only: existing parts are not rewritten.
ALTER TABLE {{db}}.content_dim
    ADD COLUMN IF NOT EXISTS show_name LowCardinality(String) DEFAULT '' AFTER category;

-- Deduplicated read view. Replacement by background merge is eventual, so the
-- dictionary source must not assume physical replacement has happened yet.
-- [official: insert-optimize-avoid-final — resolve with argMax, not FINAL]
--
-- Same principle as `events_dedup` in 003_events_clean.sql: the engine may
-- collapse, the read must not depend on whether it has.
CREATE OR REPLACE VIEW {{db}}.content_current AS
SELECT
    content_id,
    argMax(title,      source_version) AS title,
    argMax(video_type, source_version) AS video_type,
    argMax(category,   source_version) AS category,
    argMax(show_name,  source_version) AS show_name
FROM {{db}}.content_dim
GROUP BY content_id;

-- Enrichment dictionary.
--
-- A dictionary, not a JOIN: the dimension is 33K rows with 100% join coverage
-- against the event stream, and enrichment happens on the ingest/compaction hot
-- path where a right-side hash build per query would be pure waste.
-- [official: query-join-consider-alternatives — prefer a dictionary over a JOIN
--  for small, stable dimensions]
--
-- LIFETIME(MIN 300 MAX 600): the catalogue can change between loads. Note the
-- correctness caveat — a dictionary refresh does NOT retract already-enriched
-- rows. Anything denormalized from this dictionary must be re-derived by
-- explicitly re-dirtying the affected sessions.
--
-- The CLICKHOUSE source authenticates even when it points at a table on the
-- same server, so credentials are substituted here from .env at apply time
-- rather than committed. They do end up visible in SHOW CREATE DICTIONARY and
-- system.dictionaries; if that matters in your environment, replace the USER /
-- PASSWORD clauses with a named collection:
--
--   CREATE NAMED COLLECTION sonyliv_ch AS user = '...', password = '...';
--   SOURCE(CLICKHOUSE(NAME sonyliv_ch DB '{{db}}' TABLE 'content_current'))
--
-- COMPLEX_KEY_HASHED, not HASHED, for one specific reason. A simple-key
-- dictionary key is always UInt64: ClickHouse silently coerces the declared
-- Int64 (check system.dictionaries.key.types) and then every lookup on a
-- negative id throws NOT_IMPLEMENTED "cannot be safely converted into UInt64".
-- The catalogue contains exactly one such id, -987654322, written by the source
-- system as 18446744072721897294 — the id csvsrc.ParseContentID exists to
-- recover. Enriching every row correctly and then failing to look one of them
-- up would be an odd place to give up. COMPLEX_KEY_HASHED preserves the
-- declared key type; lookups pass a tuple. It costs a little more memory per
-- key than HASHED, which at 33K rows is not a consideration.
--
-- OR REPLACE rather than IF NOT EXISTS so this correction reaches a database
-- that already has the old definition. Rebuilding 33K rows is cheap.
CREATE OR REPLACE DICTIONARY {{db}}.content_dict
(
    content_id  Int64,
    title       String            DEFAULT '',
    video_type  String            DEFAULT 'unknown',
    category    String            DEFAULT 'unknown',
    show_name   String            DEFAULT ''
)
PRIMARY KEY content_id
SOURCE(CLICKHOUSE(
    DB       '{{db}}'
    TABLE    'content_current'
    USER     '{{ch_user}}'
    PASSWORD '{{ch_password}}'
))
LIFETIME(MIN 300 MAX 600)
LAYOUT(COMPLEX_KEY_HASHED());
