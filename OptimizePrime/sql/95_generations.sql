-- ============================================================================
-- 95_generations.sql — the generation-pinned serving surface (ADR 0034).
--
-- SUMMARY: a reader must never see a half-built model. Every derived tier is
-- stored generation-keyed in a `gen_*` table whose PARTITION BY and ORDER BY
-- both LEAD with `generation`; one append-only control table `model_generation`
-- names which generation is committed; serving reads go through one pinned base
-- view per tier that filters to it. A build writes a new generation and commits
-- it only after its gates pass, so a build that dies leaves the previous
-- generation serving, whole. Nothing here is destructive — this file only
-- CREATEs. The name swap that makes `cc_minute_delta` resolve to the pinned view
-- lives in tools/generation-install.sh, behind guards, deliberately NOT here:
-- tools/apply-sql.sh applies every file in sql/, and a DROP in this directory
-- would eventually be pointed at the graded database.
--
-- WHY `generation` IS IN THE SORT KEY AND NOT JUST A FILTER COLUMN.
-- ADR 0023 rejected generation gating with a correct, measured reason: on a
-- ReplacingMergeTree read through FINAL, FINAL resolves BEFORE WHERE, so an
-- uncommitted row replaces the committed one and the generation filter then
-- discards the survivor — leaving no row at all. That is true only while
-- `generation` is payload. Put it in the ORDER BY and rows of different
-- generations are different keys, so FINAL can never collapse across them.
-- Reproduced both ways in evidence/generation-pinning/10-final-vs-where.txt:
-- payload column -> 0 rows returned; key column -> the right row, every time.
--
-- WHY `generation` IS ALSO IN THE PARTITION KEY.
--   * Retiring a generation is ALTER TABLE ... DROP PARTITION — metadata only,
--     no mutation, no merge storm. Rollback is the same primitive in reverse:
--     the old generation is still on disk, so it is a control-table insert.
--   * A pinned read prunes to exactly one generation's parts. Measured: holding
--     3 generations costs the reader nothing (11.44 MiB read pinned vs 11.44 MiB
--     with a single generation present; 22.89 MiB unpinned across all three).
--
-- WHAT THE POINTER COSTS. `WHERE generation = (SELECT ...)` is a scalar
-- subquery, which ClickHouse evaluates during analysis and substitutes as a
-- constant, so partition and primary-key pruning are identical to a literal.
-- Measured: literal pin 1,000,001 rows read, subquery pin 1,000,002 (the extra
-- row IS the control table). See evidence/generation-pinning/20-pointer-cost.txt.
--
-- TRAP, and it is a silent one — see ADR 0034 "What this does not solve".
-- `SELECT ... FROM <normal view> FINAL` does NOT propagate FINAL to the view's
-- underlying table and does NOT error: it is a silent no-op returning
-- un-deduplicated rows (verified 26.7.1.1315 — 2 rows/30 instead of 1 row/20).
-- Therefore EVERY pinned base view over a ReplacingMergeTree tier below carries
-- FINAL ITSELF. Downstream views may keep their own `FINAL` — it becomes a
-- harmless no-op, verified to still return the deduplicated answer — but they
-- can no longer be relied on for it. A new pinned base view that forgets FINAL
-- breaks every reader beneath it without a single error message.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- THE CONTROL TABLE. Append-only, one row per state transition, never updated:
-- a mutation is asynchronous and a commit must be instantaneous and atomic. An
-- INSERT of one row is both. `status` moves building -> committed | abandoned,
-- and `v_active_generation` reads the newest committed one, so a rollback is
-- also an INSERT (of an `abandoned` row for the bad generation) rather than a
-- delete.
--
-- MergeTree, not Replacing: history here is the audit trail. Codex 008 §9 P0
-- asks that "evidence can name the exact generation and policy version it
-- certified" — that is what git_commit / gate_verdict / notes are for.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_generation
(
    generation   UInt32,
    -- 'building'  — rows may be landing right now; NEVER served
    -- 'committed' — gates passed; this generation is servable
    -- 'abandoned' — build died, or a committed generation was rolled back
    status       LowCardinality(String),
    at           DateTime64(3) DEFAULT now64(3),
    git_commit   String DEFAULT '',
    -- Free-form, but by convention the build's own gate lines, verbatim.
    gate_verdict String DEFAULT '',
    notes        String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (generation, at)
SETTINGS min_bytes_for_wide_part = 0;

-- THE POINTER. The newest generation whose LAST recorded status is 'committed'.
-- argMax over the whole history, not `max(generation) WHERE status='committed'`:
-- the latter cannot express a rollback, because the 'abandoned' row it would
-- need to notice is filtered out before the max is taken.
CREATE OR REPLACE VIEW v_active_generation AS
SELECT ifNull(max(generation), 0) AS generation
FROM
(
    SELECT generation, argMax(status, at) AS status
    FROM model_generation
    GROUP BY generation
)
WHERE status = 'committed';

-- Operator view: what every generation is, newest first.
CREATE OR REPLACE VIEW v_generation_status AS
SELECT
    generation,
    argMax(status, at)     AS status,
    min(at)                AS started_at,
    max(at)                AS last_at,
    argMax(git_commit, at) AS git_commit,
    generation = (SELECT generation FROM v_active_generation) AS is_active
FROM model_generation
GROUP BY generation
ORDER BY generation DESC;

-- ---------------------------------------------------------------------------
-- THE GENERATION-KEYED TIERS.
--
-- Each is its canonical definition with `generation UInt32` prepended as the
-- FIRST column (so a build can stage with `SELECT <g>, * FROM <built tier>`
-- positionally, no column list to keep in sync), leading the ORDER BY (so FINAL
-- cannot cross generations) and leading the PARTITION BY (so retirement is a
-- DROP PARTITION and a pinned read prunes exactly).
--
-- The rest of each key is UNCHANGED, so every prefix every existing view and
-- benchmark query was written against still holds — `generation` is pinned to a
-- constant on every read, which leaves the remaining prefix fully usable. In
-- particular ADR 0008's "one more dimension is a metadata-only ALTER at the tail
-- of the sort key" survives untouched.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gen_session_intervals
(
    generation       UInt32,
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    video_resolution  String ALIAS extra_dimensions['video_resolution'],
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64,
    INDEX idx_start interval_start TYPE minmax GRANULARITY 1
)
ENGINE = ReplacingMergeTree(build_version)
PARTITION BY generation
ORDER BY (generation, video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

ALTER TABLE gen_session_intervals
    ADD COLUMN IF NOT EXISTS extra_dimensions Map(LowCardinality(String), String) DEFAULT map() AFTER player_version,
    ADD COLUMN IF NOT EXISTS video_resolution String ALIAS extra_dimensions['video_resolution'] AFTER extra_dimensions;

CREATE TABLE IF NOT EXISTS gen_cc_minute_delta
(
    generation  UInt32,
    minute      DateTime,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    content_id  Int64,
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    audio_language    LowCardinality(String),
    app_version       LowCardinality(String),
    delta       SimpleAggregateFunction(sum, Int64),
    starts      SimpleAggregateFunction(sum, Int64),
    ends        SimpleAggregateFunction(sum, Int64)
)
ENGINE = AggregatingMergeTree
-- Day stays in the partition key: every existing partition-pruning claim about
-- this tier (ADR 0003) is unchanged, generation just splits each day's parts by
-- generation as well.
PARTITION BY (generation, toYYYYMMDD(minute))
ORDER BY (generation, platform, country, content_id, minute,
          subtitle_language, player_version, audio_language, app_version)
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS gen_cc_hour_agg
(
    generation  UInt32,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    content_id  Int64,
    cube_level  UInt8,
    hour        DateTime,
    peak        Int64,
    peak_minute DateTime,
    integral    Int64,
    computed_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(computed_at)
PARTITION BY (generation, toYYYYMM(hour))
ORDER BY (generation, platform, country, content_id, cube_level, hour)
SETTINGS index_granularity = 8192,
         min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS gen_cc_user_minute
(
    generation   UInt32,
    minute       DateTime,
    platform     LowCardinality(String),
    country      LowCardinality(String),
    content_id   Int64,
    active_state AggregateFunction(uniqExact, String),
    computed_at  DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(computed_at)
PARTITION BY (generation, toYYYYMMDD(minute))
ORDER BY (generation, platform, country, content_id, minute)
SETTINGS min_bytes_for_wide_part = 0;

-- ---------------------------------------------------------------------------
-- THE PINNED BASE VIEWS — the whole serving contract, in four definitions.
--
-- Created here under `p_*` names, which is what makes this file safe to apply
-- anywhere. tools/generation-install.sh is what re-points the canonical names
-- (`cc_minute_delta` etc.) at these, on a database that is being converted;
-- after that step every existing downstream view and benchmark query reads a
-- pinned generation without a single edit.
--
-- `* EXCEPT generation` keeps the column list and its ORDER identical to the
-- unpinned tier, which is the property that makes the swap invisible upstream.
-- FINAL is carried HERE for the two Replacing tiers, for the reason in the
-- header: a downstream FINAL over a view is a silent no-op.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW p_session_intervals AS
SELECT * EXCEPT generation,
       extra_dimensions['video_resolution'] AS video_resolution
FROM gen_session_intervals FINAL
WHERE generation = (SELECT generation FROM v_active_generation);

CREATE OR REPLACE VIEW p_cc_minute_delta AS
SELECT * EXCEPT generation
FROM gen_cc_minute_delta
WHERE generation = (SELECT generation FROM v_active_generation);

CREATE OR REPLACE VIEW p_cc_hour_agg AS
SELECT * EXCEPT generation
FROM gen_cc_hour_agg FINAL
WHERE generation = (SELECT generation FROM v_active_generation);

CREATE OR REPLACE VIEW p_cc_user_minute AS
SELECT * EXCEPT generation
FROM gen_cc_user_minute FINAL
WHERE generation = (SELECT generation FROM v_active_generation);
