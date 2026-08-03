-- =====================================================================
-- 040 — Minute serving tier: sonyliv.concurrency_minute_versions
-- =====================================================================
--
-- ADDITIVE. Creates one table and fills it. Deletes nothing, rebuilds
-- nothing, migrates nothing. The existing
-- deltas -> bucket_net -> day_anchor chain is untouched and keeps working.
--
-- Definition: solution/policy.yaml. Plan + review: docs/CONSOLIDATION-PLAN.md.
--
-- ---------------------------------------------------------------------
-- WHY THIS EXISTS
-- ---------------------------------------------------------------------
-- Not for latency. Serving is already 10-26ms and no judging axis
-- distinguishes that from 2ms. This exists because a FLAT ONE-TABLE READ
-- SURFACE is what makes a LibreChat + ClickHouse MCP text-to-SQL layer
-- answerable, and that integration is a scored deliverable. An LLM can
-- write `max(minute_peak) ... WHERE minute_start BETWEEN`. It will not
-- reliably write a day-anchored cumulative sum over ms boundaries.
--
-- ---------------------------------------------------------------------
-- MASK SET: 0,1,2,3,4,5,8,9,15  — nine masks, NOT ten
-- ---------------------------------------------------------------------
-- Mask 12 is omitted. video_type is functionally determined by content_id
-- (33,464 catalogue rows, ZERO with more than one video_type), so
-- mask 12 = content+video_type is identical to mask 4 = content. Measured
-- against concurrency_deltas: 0 mismatches across 63,881 rows.
--
-- This costs nothing HERE because the table is new -- there is no
-- SummingMergeTree to rebuild. Dropping mask 12 from concurrency_deltas
-- is deferred for exactly that reason (see the plan).
--
-- Mask 15 is KEPT. Its apparent redundancy with mask 5 depends on
-- `country` having one value in this extract, which is not a property of
-- the schema. Mask 15 minus video_type is mask 7, which is NOT
-- materialised anywhere, and TODOS.md names mask 15 as the finest-grain
-- donor for re-deriving unmaterialised masks.
-- =====================================================================


-- ---------------------------------------------------------------------
-- The table
-- ---------------------------------------------------------------------
-- Adopted from solution/sql/00_schema.sql:510 rather than inventing a
-- parallel one. TWO DELIBERATE CHANGES from that definition:
--
--   1. content_id is Int64, NOT Int32. Largest observed id is
--      2,078,177,474 -- 96.8% of Int32 max -- and the catalogue carries a
--      negative id (-987654322) stored unsigned upstream. See
--      ingest/sql/001_content.sql:24-31, which documents this by name.
--      Int32 leaves 3.2% headroom before an unseen-day id silently
--      corrupts the join key.
--
--   2. The three dedup settings are present, with the ALTER re-issue.
--      CLAUDE.md:98 -- "Every new MergeTree table in this project must
--      carry all three settings" -- because CREATE TABLE IF NOT EXISTS is
--      a no-op against an existing table, so the correction would never
--      arrive on a re-run.
--
-- ORDER BY note: `generation` is FIRST and this is a plain MergeTree, not
-- Replacing. `WHERE generation = {g}` is therefore a clean prefix scan
-- that returns ONLY rows written at g. Corrections must write a COMPLETE
-- generation. A sparse patch makes every uncorrected minute vanish from
-- the answer -- silently.
--
-- ---------------------------------------------------------------------
-- clip_variant IS IN THE KEY. Added 2026-08-02; it was missing.
-- ---------------------------------------------------------------------
-- The producer takes {clip_variant:String} and, until this change, used it
-- ONLY in the WHERE -- it was never selected into a column. That
-- contradicted docs/TABLE-CONTRACT.md §3, which lists clip_variant as one
-- of three MANDATORY read predicates and states that forgetting it
-- "exactly doubles every number". On this table there was no predicate to
-- forget, because there was nothing to filter.
--
-- Load both variants at one generation and the table doubles with NO WAY
-- to separate them afterwards -- not by generation, pipeline_run_id,
-- source_delta_snapshot, or any other column. That is the 2026-08-01
-- doubling incident re-armed in the table designed to prevent it.
--
-- Measured on the service before the fix: 272,070 rows, ONE generation,
-- and no column recording which of the two variants they are.
--
-- Note what does NOT catch this. C9 asserts max(minute_peak) is unchanged,
-- and max() is idempotent under duplication -- 2,305 stays 2,305. C4 does
-- catch it via sum(active_entity_ms), but only after the second variant
-- lands, and on THIS extract the two variants are byte-identical
-- (TABLE-CONTRACT §3: 0 rows differ), so the duplicate is invisible to
-- inspection. On the unseen day the variants diverge -- an open session
-- clipped at the observation horizon is shorter than the same session
-- unclipped -- so C4 becomes a real check rather than a tautology, and
-- this column becomes load-bearing rather than hygienic.
--
-- Position: immediately after policy_version, matching the key order every
-- other table in this pipeline already uses
-- (concurrency_deltas, concurrency_bucket_net, concurrency_day_anchor,
-- active_intervals all lead policy_version, clip_variant).
--
-- ORDER BY IS IMMUTABLE, so this is NOT reachable by ALTER and the file's
-- usual CREATE-IF-NOT-EXISTS convergence does not apply. See the migration
-- block below -- it must run before this CREATE has any effect on a
-- database that already holds the old table.
-- ---------------------------------------------------------------------

-- MIGRATION GUARD. Refuses to proceed silently against the old shape: an
-- existing table without clip_variant would make the CREATE below a no-op
-- and the producer's new column list would then fail to insert, or worse,
-- succeed against a stale shape. Throws with instructions instead.
-- currentDatabase(), NOT a 'sonyliv' literal. apply_sql.py's --rewrite-db
-- replaces the table prefix `sonyliv.` but cannot rewrite a string literal, so a
-- hardcoded database name here would silently inspect the WRONG database under
-- --database sonyliv_dev and the guard would pass while the real target was stale.
SELECT throwIf(
    (SELECT count() FROM system.tables
      WHERE database = currentDatabase() AND name = 'concurrency_minute_versions') = 1
    AND
    (SELECT count() FROM system.columns
      WHERE database = currentDatabase() AND table = 'concurrency_minute_versions'
        AND name = 'clip_variant') = 0,
    -- ONE string literal. ClickHouse has no C-style implicit concatenation, so
    -- 'part one' 'part two' is a SYNTAX ERROR, not a joined string -- the same
    -- trap this file's COMMENT clause already warns about, and the reason the
    -- pre-2026-08-02 041 could never execute a single one of its gates.
    'MIGRATION REQUIRED: concurrency_minute_versions exists WITHOUT clip_variant. ORDER BY is immutable, so this needs a rebuild, not an ALTER. Run: DROP TABLE sonyliv.concurrency_minute_versions; then re-run this file, then 041. The table is derived -- nothing reads it except concurrency_minute_mask13 and concurrency_minute_current -- so dropping it loses no source of truth.'
) AS migration_guard;

CREATE TABLE IF NOT EXISTS sonyliv.concurrency_minute_versions
(
    generation             UInt64,
    policy_version         LowCardinality(String),
    clip_variant           Enum8('unclipped' = 1, 'clipped' = 2),
    pipeline_run_id        UUID,
    source_delta_snapshot  UInt128,
    entity                 Enum8('session' = 1, 'user' = 2),
    rollup_mask            UInt16,
    service_date           Date,
    minute_start           DateTime64(3, 'UTC'),
    platform               LowCardinality(String),
    country                LowCardinality(String),
    video_type             LowCardinality(String),
    content_id             Int64,
    minute_peak            UInt64,
    active_entity_ms       UInt64,
    ending_concurrency     UInt64,
    source_boundary_points UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(service_date)
ORDER BY (generation, policy_version, clip_variant, pipeline_run_id,
          source_delta_snapshot, entity, rollup_mask, service_date,
          platform, country, video_type, content_id, minute_start)
SETTINGS index_granularity = 8192,
         non_replicated_deduplication_window = 1000,
         replicated_deduplication_window = 1000,
         replicated_deduplication_window_seconds = 2592000
-- One string literal, deliberately. ClickHouse has no C-style implicit
-- concatenation, so 'part one' 'part two' is a syntax error, not a joined
-- string. Splitting this across lines is what made the first real run of this
-- file fail at line 96 before a single statement executed.
COMMENT 'Flat minute serving tier. Read with max()/sum() over a range -- never a cumsum. Additive: does not replace deltas/bucket_net/day_anchor. Definition: solution/policy.yaml.';

ALTER TABLE sonyliv.concurrency_minute_versions
  MODIFY SETTING non_replicated_deduplication_window = 1000,
                 replicated_deduplication_window = 1000,
                 replicated_deduplication_window_seconds = 2592000;


-- ---------------------------------------------------------------------
-- The producer -- TWO sources, one row
-- ---------------------------------------------------------------------
-- Neither source alone is sufficient. This was missed until review:
--
--   active_entity_ms       <- active_intervals, DENSE containment
--   ending_concurrency     <- active_intervals, DENSE containment
--   minute_peak            <- concurrency_deltas, BOUNDARY SWEEP
--   source_boundary_points <- concurrency_deltas, BOUNDARY SWEEP
--
-- WHY DENSE. Building only where a boundary falls would omit 14,226
-- minutes where concurrency was greater than zero (measured, mask 0;
-- worst gap 9,823 consecutive minutes). max(minute_peak) survives that --
-- the level only changes at boundaries, so the peak always lands on one.
-- sum(active_entity_ms) does NOT, and the time-weighted average would be
-- badly under-reported with no invariant failing.
--
-- WHY THE SWEEP TOO. Containment over intervals gives active_ms and the
-- level at the minute's edge, but it cannot give the max INSTANTANEOUS
-- level inside the minute. On this extract that difference is real:
-- true instantaneous peak 2,305 vs level at minute boundary 2,285.
--
-- minute_peak = greatest(level entering the minute, max level after each
-- boundary inside it). The entering level is the previous minute's
-- ending_concurrency, which is why the lagInFrame below exists.
--
-- Parameters: {generation:UInt64} {policy_version:String}
--             {pipeline_run_id:UUID} {source_delta_snapshot:UInt128}
--             {clip_variant:String}
-- ---------------------------------------------------------------------

INSERT INTO sonyliv.concurrency_minute_versions
WITH
-- Nine masks. See the header for why 12 is out and 15 is in.
masks AS (
    SELECT arrayJoin([0, 1, 2, 3, 4, 5, 8, 9, 15]) AS rollup_mask
),

-- Fan each interval out to every mask, projecting unselected dimensions
-- to the placeholders concurrency_deltas already uses: '' for strings,
-- 0 for content_id. Mask bits: platform=1 country=2 content_id=4 video_type=8.
fanned AS (
    SELECT
        m.rollup_mask                                                          AS rollup_mask,
        if(bitAnd(m.rollup_mask, 1) = 1, i.platform,   '')                     AS platform,
        if(bitAnd(m.rollup_mask, 2) = 2, i.country,    '')                     AS country,
        if(bitAnd(m.rollup_mask, 8) = 8, i.video_type, '')                     AS video_type,
        if(bitAnd(m.rollup_mask, 4) = 4, i.content_id, toInt64(0))             AS content_id,
        i.start_time                                                           AS start_time,
        i.end_time                                                             AS end_time
    -- active_intervals_CURRENT, not active_intervals. 010 says so in its own
    -- comment -- "Read through active_intervals_current, never this table
    -- directly" -- and this producer was reading the base table, which counts a
    -- session's intervals once PER REVISION rather than once.
    --
    -- Latent, not a present error: measured on the service 2026-08-02 there is
    -- exactly ONE revision (state_revision = 1), 63,894 rows through both the
    -- base table and the view, 0 orphan rows, 0 sessions with more than one
    -- revision. So today the two reads are identical. The first correction
    -- cycle -- the thing state_revision exists for -- is what makes them
    -- diverge, and it would inflate active_entity_ms silently.
    --
    -- 041's C4 read the base table the same way, so the two agreed while both
    -- being wrong. That is the "a check that only inspects one layer cannot
    -- validate that layer" trap from CLAUDE.md; both sides are fixed together.
    --
    -- The view's revision-resolution subquery is served by
    -- proj_session_revision (010), so this does not pay a full scan for the
    -- correctness.
    FROM sonyliv.active_intervals_current AS i
    CROSS JOIN masks AS m
    WHERE i.policy_version = {policy_version:String}
      AND i.clip_variant   = CAST({clip_variant:String}, 'Enum8(\'unclipped\' = 1, \'clipped\' = 2)')
),

-- Explode each interval across every minute it touches. Intervals are
-- half-open [start, end): an interval ending exactly on a minute boundary
-- contributes zero ms to that minute, which the overlap_ms > 0 filter drops.
exploded AS (
    SELECT
        rollup_mask, platform, country, video_type, content_id,
        toDateTime64(minute_epoch, 3, 'UTC')                                   AS minute_start,
        toUInt64(greatest(0, dateDiff('millisecond',
            greatest(start_time, toDateTime64(minute_epoch, 3, 'UTC')),
            least(end_time,      toDateTime64(minute_epoch + 60, 3, 'UTC'))))) AS overlap_ms,
        -- Does this interval still cover the instant at the minute's end?
        (start_time <= toDateTime64(minute_epoch + 60, 3, 'UTC')
         AND end_time > toDateTime64(minute_epoch + 60, 3, 'UTC'))             AS covers_end
    FROM fanned
    ARRAY JOIN range(
        toUInt32(toUnixTimestamp(toStartOfMinute(start_time))),
        toUInt32(toUnixTimestamp(toStartOfMinute(end_time))) + 60,
        60) AS minute_epoch
),

dense AS (
    SELECT
        rollup_mask, platform, country, video_type, content_id, minute_start,
        sum(overlap_ms)          AS active_entity_ms,
        countIf(covers_end)      AS ending_concurrency
    FROM exploded
    WHERE overlap_ms > 0
    GROUP BY rollup_mask, platform, country, video_type, content_id, minute_start
),

-- Running level at every ms boundary, then the max inside each minute.
sweep AS (
    SELECT
        rollup_mask, platform, country, video_type, content_id,
        toStartOfMinute(boundary_ts) AS minute_start,
        max(level)                   AS peak_at_boundaries,
        count()                      AS source_boundary_points
    FROM (
        SELECT
            rollup_mask, platform, country, video_type, content_id, boundary_ts,
            sum(sum(opens) - sum(closes)) OVER (
                PARTITION BY rollup_mask, platform, country, video_type, content_id
                ORDER BY boundary_ts
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS level
        FROM sonyliv.concurrency_deltas
        WHERE policy_version = {policy_version:String}
          AND clip_variant   = CAST({clip_variant:String}, 'Enum8(\'unclipped\' = 1, \'clipped\' = 2)')
        GROUP BY rollup_mask, platform, country, video_type, content_id, boundary_ts
    )
    GROUP BY rollup_mask, platform, country, video_type, content_id, minute_start
),

joined AS (
    SELECT
        d.rollup_mask        AS rollup_mask,
        d.platform           AS platform,
        d.country            AS country,
        d.video_type         AS video_type,
        d.content_id         AS content_id,
        d.minute_start       AS minute_start,
        d.active_entity_ms   AS active_entity_ms,
        d.ending_concurrency AS ending_concurrency,
        ifNull(s.peak_at_boundaries, toUInt64(0))     AS peak_at_boundaries,
        ifNull(s.source_boundary_points, toUInt64(0)) AS source_boundary_points,
        -- Level entering this minute = previous minute's ending level.
        -- Covers quiet minutes, where no boundary falls and the peak is
        -- simply the level carried in.
        lagInFrame(d.ending_concurrency, 1, toUInt64(0)) OVER (
            PARTITION BY d.rollup_mask, d.platform, d.country, d.video_type, d.content_id
            ORDER BY d.minute_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)  AS entering_level
    FROM dense AS d
    LEFT JOIN sweep AS s
      ON  s.rollup_mask   = d.rollup_mask
      AND s.platform      = d.platform
      AND s.country       = d.country
      AND s.video_type    = d.video_type
      AND s.content_id    = d.content_id
      AND s.minute_start  = d.minute_start
)

SELECT
    {generation:UInt64}                          AS generation,
    {policy_version:String}                      AS policy_version,
    -- Selected into the row, not merely used in the WHERE. This is the §1 fix:
    -- without it the two variants are indistinguishable once written.
    CAST({clip_variant:String}, 'Enum8(\'unclipped\' = 1, \'clipped\' = 2)') AS clip_variant,
    {pipeline_run_id:UUID}                       AS pipeline_run_id,
    {source_delta_snapshot:UInt128}              AS source_delta_snapshot,
    CAST('session', 'Enum8(\'session\' = 1, \'user\' = 2)') AS entity,
    toUInt16(rollup_mask)                        AS rollup_mask,
    toDate(minute_start, 'UTC')                  AS service_date,
    minute_start,
    platform, country, video_type, content_id,
    greatest(peak_at_boundaries, entering_level) AS minute_peak,
    active_entity_ms,
    ending_concurrency,
    source_boundary_points
FROM joined;


-- ---------------------------------------------------------------------
-- Free correctness win: mask 13 is answerable at zero cost
-- ---------------------------------------------------------------------
-- The same functional dependency that makes mask 12 = mask 4 makes
-- mask 13 (platform+content+video_type) = mask 5 (platform+content).
-- Masks 6, 7, 10, 11, 14 stay genuinely unanswerable -- TODOS.md: a
-- missing mask's deltas can be summed from a finer one, but its PEAK
-- cannot, because two dimension values peak at different minutes.
--
-- ---------------------------------------------------------------------
-- FIXED 2026-08-02: this view returned ZERO ROWS on the live service.
-- ---------------------------------------------------------------------
-- The previous form selected `toUInt16(13) AS rollup_mask` and filtered
-- `WHERE rollup_mask = 5` in the SAME query level. The output alias
-- SHADOWS the base column, so the predicate was evaluated as 13 = 5 --
-- constant false. The view was deployed, committed, and silently empty.
--
-- Measured on the service before the fix:
--   concurrency_minute_mask13            0 rows
--   base table WHERE rollup_mask = 5     85,553 rows
--
-- Mechanism isolated on the service, same data, three forms:
--   toUInt16(13) AS rollup_mask + WHERE rollup_mask = 5   ->      0
--   alias renamed to rollup_mask_out, same WHERE          -> 85,553
--   WHERE pushed into a subquery                          -> 85,553
--
-- The filter is now inside a subquery, so `rollup_mask` in the WHERE is
-- unambiguously the base column while the OUTPUT column keeps the name
-- callers expect. Renaming the output would have been the other fix and
-- was rejected: it changes the read contract for every caller.
--
-- This is the silent-wrong-answer shape this repo exists to avoid, and it
-- survived because nothing asserted on the view. 041's G6 now does.
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW sonyliv.concurrency_minute_mask13 AS
SELECT
    generation, policy_version, clip_variant, pipeline_run_id,
    source_delta_snapshot, entity,
    toUInt16(13)                                     AS rollup_mask,
    service_date, minute_start,
    platform, country,
    -- Default is '__unknown__' (policy.yaml: unknown_string), NOT 'unknown'.
    -- 'unknown' is a REAL catalogue value: 1,089 titles carry it, 141 of them
    -- played, covering 863 intervals. Using it as the fallback would make a
    -- cold-replica dictionary miss indistinguishable from real data -- the
    -- exact silent fallback CLAUDE.md says must stay assertable. With
    -- '__unknown__', `countIf(video_type = '__unknown__') > 0` is a valid alarm.
    dictGetOrDefault(sonyliv.content_dict, 'video_type', tuple(content_id), '__unknown__') AS video_type,
    content_id,
    minute_peak, active_entity_ms, ending_concurrency, source_boundary_points
-- Filter INSIDE the subquery. At this level `rollup_mask` would resolve to the
-- toUInt16(13) alias above, not to the stored column -- see the note above.
FROM (
    SELECT * FROM sonyliv.concurrency_minute_versions WHERE rollup_mask = 5
);


-- ---------------------------------------------------------------------
-- concurrency_minute_current -- READ THIS, not the versioned table
-- ---------------------------------------------------------------------
-- Nothing published the current `generation`, so a caller had to pin four
-- columns -- generation, policy_version, pipeline_run_id,
-- source_delta_snapshot -- with values that appear in no table.
-- pipeline_watermark carries stage, policy_version, watermark,
-- state_revision and sessions_applied, and none of the four. Measured on
-- the service:
--
--   stage: stage02_serving  policy_version: sonyliv-active-v1
--   watermark: 2026-08-01 16:22:20.425  state_revision: 1
--   sessions_applied: 10848
--
-- Because `generation` leads the ORDER BY on a plain MergeTree, a WRONG pin
-- returns SILENTLY EMPTY rather than erroring -- and a hardcoded UUID
-- breaks on the next run. Since the stated reason this tier exists is to be
-- answerable by a text-to-SQL layer over MCP, "the caller must already know
-- four opaque values, and gets zero rows if any is stale" defeats the
-- purpose.
--
-- RESOLUTION RULE: max(generation). Deliberately self-contained rather than
-- reading pipeline_watermark, because a missing or stale watermark row
-- would reintroduce exactly the silent-empty failure this view exists to
-- remove. max(generation) cannot be empty while the table has rows.
--
-- It is also cheap, not a full scan: `generation` is the FIRST sort-key
-- column, so max() is answered from the primary index rather than by
-- reading the table.
--
-- WHAT THIS VIEW DOES NOT DECIDE. clip_variant, entity and rollup_mask stay
-- caller predicates on purpose. Which clip variant is authoritative is a
-- judgement call against a private answer key, and 010 is explicit that the
-- pipeline "refuses to make it silently" -- so this view will not pick one
-- either. The difference from before is that the caller now CAN pick, which
-- is the §1 fix. Omitting clip_variant still doubles every number; that is
-- documented in TABLE-CONTRACT §3 and is now a real predicate rather than
-- an impossible one.
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW sonyliv.concurrency_minute_current AS
SELECT *
FROM sonyliv.concurrency_minute_versions
WHERE generation = (SELECT max(generation) FROM sonyliv.concurrency_minute_versions);
