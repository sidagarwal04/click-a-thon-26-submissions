-- ============================================================================
-- Stage 02 target: the serving layer.
--
-- Two questions, two structures. Conflating them is the mistake this file
-- exists to avoid:
--
--   "how many are live RIGHT NOW?"   -> session_live_state
--                                       O(open sessions). Never touches history.
--                                       Identical cost on day 1 and day 300.
--
--   "what was the peak in [W0,W1)?"  -> concurrency_deltas + concurrency_bucket_net
--                                       O(checkpoints before W0) + O(deltas inside).
--                                       Never touches open sessions.
--
-- A single running-sum-from-epoch answers both and scales for neither: a prefix
-- sum reads from t=0 by construction, and no sort key, skip index or projection
-- prunes it. Measured on this service: a 30-second window predicate on
-- events_clean still read 834,364 of 901,348 rows (92.6%), because event_ts is
-- not the sort-key prefix. "Incremental" over a time predicate is a full scan
-- wearing a filter.
--
-- Apply with:
--   clickhouse-client --multiquery < pipeline/sql/020_serving_layer.sql
--
-- PREREQUISITE: pipeline/sql/010_active_intervals.sql. As of writing,
-- active_intervals is NOT deployed on the service -- system.tables shows only
-- the ingest objects. Everything here is fed from it.
--
-- Idempotent and converging, same pattern as 010 and ingest/sql/002: every
-- CREATE is IF NOT EXISTS and every settings block is re-issued as
-- ALTER ... MODIFY SETTING, because CREATE TABLE IF NOT EXISTS is a no-op
-- against an existing table and the correction would otherwise never arrive.
-- ============================================================================


-- ============================================================================
-- PART 1 -- "how many are live right now?"
-- ============================================================================

-- ----------------------------------------------------------------------------
-- session_live_state
--
-- One resolved row per session, holding the state as of the latest recompaction.
-- This is the correct half of the "keep a lightweight per-session row" idea: a
-- per-session row read against now(), with the predicate and the engine both
-- fixed. What was wrong with the original shape:
--
--   * SummingMergeTree cannot hold a "latest timestamp". DateTime64 overrides
--     isSummable() -> false, so SummingSortedAlgorithm neither sums nor maxes
--     it; setRow() runs only in startGroup() and addRow() never refreshes it,
--     so the survivor is the FIRST row in merge order -- systematically the
--     OLDEST value. Measured spread between a session's earliest and latest
--     candidate timestamp: 100% of sessions can be wrong, p50 714 s, p99
--     4,447 s, max 43.6 h, and 91.05% exceed 60 s. Keeping the oldest makes the
--     lease read as already expired: a systematic undercount, silent, and
--     non-deterministic in time because it depends on merge order.
--
--   * With no explicit `columns` list SummingMergeTree also sums every other
--     summable column -- content_id and user_key included. Measured: 96.7% of
--     sessions exceed 2^64, 49.6% land BELOW a single input, and a wrapped
--     user_key averaging ~9.2e18 passes every plausibility check. A corrupted
--     content_id then misses content_dict entirely and every row silently takes
--     the fallback -- the exact failure CLAUDE.md already documents.
--
--   * "last event that is not a pause" is not the activity model. Measured at
--     the policy 120 s timeout it gives peak 2,886 against 2,305 (+25.2%) and
--     15,539 intervals against 31,947 (-51.4%) -- two errors in OPPOSITE
--     directions, so no single sanity check catches both. It is also a strict
--     over-counter (false-live sessions 10,866/10,866, false-dead 0), so no
--     "rule says live but session does not exist" check will ever fire. And it
--     cannot be calibrated away: the hourly rule/true ratio ranges 1.0268 to
--     1.3436 (sigma 0.0793), so a single constant leaves -19%..+7% per hour.
--
-- ENGINE. AggregatingMergeTree, not Summing, not Replacing, not Coalescing:
--   * argMax is NOT on the SimpleAggregateFunction whitelist (measured: any,
--     anyLast, min, max, sum, sumWithOverflow, groupBitAnd/Or/Xor, sumMap,
--     min/maxMap, groupArrayArray, groupUniqArrayArray, ...), so the
--     revision-resolved fields need full -State/-Merge.
--   * SimpleAggregateFunction(max, DateTime64) WOULD be legal and is even
--     honoured by SummingMergeTree -- but max is wrong under revisions. A late
--     pause can move a lease BACKWARD, and the correct value is the one from
--     the highest revision, not the highest value. argMax by state_revision is
--     revision-correct; max is a ratchet.
--   * ReplacingMergeTree(row_version) is measurably wrong here: row_version is
--     an ingest-order counter, and argMax(event_ts, row_version) != max(event_ts)
--     for 6,609 of 10,866 sessions (60.8%).
--   * CoalescingMergeTree resolves with last_value -- last in MERGE order, not
--     latest by event_ts. Same bug class as Summing, different survivor rule.
--
-- READ PATH. Always argMaxMerge under GROUP BY session_key. Never FINAL, never
-- a bare SELECT. -Merge is correct against a completely unmerged table, which
-- matters because merge is eventual and may never happen: partition 20260726
-- sat at 2 parts for 115 minutes with 0 merges running and merge_selector_base
-- = 5 gives no reason it ever would. A permanently 2-part state is a better
-- argument for read-time aggregation than any finite merge lag, because it
-- never resolves.
--
--     SELECT count() AS live_now
--     FROM (
--         SELECT session_key,
--                argMaxMerge(lease_expiry)  AS lease_expiry,
--                argMaxMerge(is_active_now) AS active,
--                argMaxMerge(is_terminated) AS terminated
--         FROM sonyliv.session_live_state
--         WHERE policy_version = 'sonyliv-active-v1'
--         GROUP BY session_key
--     )
--     WHERE terminated = 0 AND active = 1 AND lease_expiry > now64(3, 'UTC');
--
-- The lease is evaluated AT READ TIME against now(). That is the only place it
-- can be evaluated: an interval's lease-expiry end is a wall-clock instant at
-- which, by definition, no event arrives, so no insert-time construction can
-- ever write that row.
--
-- SORT KEY. (policy_version, session_key). policy_version leads for the same
-- reason as in 010 -- side-by-side answers under contested semantics, and
-- ORDER BY is immutable so it is either here or never. With it fixed by the
-- WHERE clause, GROUP BY session_key is an exact sort-key prefix and can stream
-- instead of re-sorting.
--
-- Not partitioned, same reasoning as 010 at this size.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.session_live_state
(
    policy_version      LowCardinality(String) COMMENT 'Semantic contract; see solution/policy.yaml',
    session_key         UInt64,

    -- Monotone by construction (it is the recompaction cycle id), so max is
    -- correct here where it is wrong for every field below.
    state_revision      SimpleAggregateFunction(max, UInt64),

    -- last_eligible_signal + heartbeat_timeout_ms, as of the winning revision.
    -- Compared against now64(3) at read time; never pre-evaluated.
    lease_expiry        AggregateFunction(argMax, DateTime64(3, 'UTC'), UInt64),

    -- The THREE-AXIS conjunction at the session's last event: play/pause AND
    -- foreground AND lease-eligible. Not "the last event was not a pause".
    -- Measured: gating on running play/pause state alone already takes active
    -- time inflation from +26.12% to +0.27% and affected sessions from 10,866
    -- to 1,932, with the entire residual being the foreground axis. Because the
    -- recompaction computes the full three-axis state anyway, taking it from
    -- there makes the residual zero by construction rather than small.
    is_active_now       AggregateFunction(argMax, UInt8, UInt64),

    -- A VideoSessionEnd was observed. Distinct from an expired lease: a
    -- terminated session can never come back, a lapsed one can.
    is_terminated       AggregateFunction(argMax, UInt8, UInt64),

    -- Start of the currently-open interval, if any. This interval is
    -- deliberately NOT in concurrency_deltas -- see the sealing note there.
    open_interval_start AggregateFunction(argMax, DateTime64(3, 'UTC'), UInt64),

    user_key            AggregateFunction(argMax, UInt64, UInt64),
    content_id          AggregateFunction(argMax, Int64,  UInt64),

    -- Declared String, not LowCardinality(String), because that is what the
    -- server stores. Measured on 26.2.1.525:
    --   toTypeName(initializeAggregation('argMaxState', toLowCardinality('X'), toUInt64(1)))
    --     -> AggregateFunction(argMax, String, UInt64)
    -- The LowCardinality wrapper is dropped inside AggregateFunction. Writing
    -- it would make the DDL disagree with SHOW CREATE TABLE for no benefit.
    platform            AggregateFunction(argMax, String, UInt64),
    country             AggregateFunction(argMax, String, UInt64),
    video_type          AggregateFunction(argMax, String, UInt64),

    recompacted_at      SimpleAggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (policy_version, session_key)
SETTINGS
    -- Cloud substitutes SharedMergeTree for MergeTree, which moves insert
    -- deduplication onto the replicated window -- and that one expires on a
    -- timer, server default 3600 s. Without all three, a re-run is a no-op for
    -- exactly one hour and then silently doubles the table. See
    -- ingest/sql/002_events_raw.sql, which had to be corrected for this.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Current per-session state. Read via argMaxMerge GROUP BY session_key, never FINAL.';

ALTER TABLE sonyliv.session_live_state
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;

-- RETENTION IS DELIBERATELY ABSENT, not forgotten. The invariant is sharp: any
-- deletion must remove ALL revisions of a session or none. If one revision of a
-- session is deleted and an older one survives, the older one wins the argMax
-- and resurrects stale state -- a silent wrong answer with no error anywhere.
--
-- That rules out the obvious `TTL lease_expiry + INTERVAL n DAY`: TTL is
-- evaluated per row at merge time, and revisions of the same session carry
-- DIFFERENT lease_expiry values, so it deletes them piecemeal. It also rules
-- out a TTL on any field the recompaction can revise.
--
-- The safe procedure is a tombstone sweep: the recompaction writes a terminal
-- revision, and a periodic job issues DELETE WHERE session_key IN (...), whose
-- predicate is on the whole key and is therefore all-or-nothing by
-- construction. At the extract's 10,866 sessions this is not yet needed; at a
-- projected 12.0M sessions/day it is. Decide it explicitly before running at
-- scale rather than reaching for a TTL.


-- ============================================================================
-- PART 2 -- "what was the peak in a historical window?"
-- ============================================================================

-- ----------------------------------------------------------------------------
-- concurrency_deltas
--
-- Millisecond-exact signed interval boundaries. A running sum of these IS the
-- concurrency curve -- that part of the original idea is right and is how the
-- oracle in solution/sql/30_exact_metrics.sql already works. What must change
-- is WHERE the signs come from: interval boundaries, never raw events.
--
-- Mapping event types straight to +1/-1 fails for a reason no amount of
-- mapping-tuning repairs. Measured over events_clean: the running total ends at
-- +14,632 instead of 0, peaks at 15,452 against a true 2,305 (6.7x), goes
-- NEGATIVE for 487 sessions, and 99.82% of sessions are counted more than once
-- concurrently -- one reaches 30. Root cause is level-triggered versus
-- edge-triggered emission: 33.77% of `resume` events fire while the session is
-- not paused. And the fix is not available at insert time, because an
-- incremental MV sees only its own block and therefore cannot know whether an
-- event changed anything. The charitable 2-signal mapping fails too (ends -4).
--
-- SEALED INTERVALS ONLY. An open session's trailing interval end moves forward
-- with every liveness ping -- 780,754 of 901,348 events here, 93% of the
-- stream. Publishing open tails would mean retracting and re-adding each open
-- session's boundary on every ping: projected ~930M retract+add pairs/day at
-- 1B events/day. The open tail lives in session_live_state instead. This is the
-- concrete reason the two questions need two structures.
--
-- ENGINE. SummingMergeTree with an EXPLICIT column list.
--   * CollapsingMergeTree is wrong: it reduces each key group to at most two
--     rows and keeps one state row, so a bucket with net +26 collapses to a
--     single Sign=+1 and sum(Sign) returns 1, not 26. Measured cumulative
--     damage 86.9% undercount. Magnitude is exactly what a delta table needs.
--     It is also not a storage win -- real Collapsing leaves 1.11x Summing.
--   * The explicit (opens, closes) list is not cosmetic. Bare SummingMergeTree
--     sums every summable non-key column, which is how content_id and user_key
--     get destroyed elsewhere in this design.
--
-- opens/closes as SEPARATE counters, not a single signed `delta`:
--   * SummingMergeTree deletes a row when every summed column is zero. A
--     spike-and-return bucket nets to zero and VANISHES on merge. Measured on
--     the real boundary stream: 404 of 1,796 minute buckets (22.5%) and 27 of
--     96 hour buckets (28.1%) have net = 0. With separate counters a real
--     bucket is never all-zero, so the row survives.
--   * The deletion is also non-deterministic in time -- it needs the balancing
--     rows to meet in one merge -- so the same audit query returns different
--     bucket counts over time for identical data.
--   Today's answer happens to be unaffected (peak with all zero-net buckets
--   removed is still 2,305), so this is a latent hole, not a present error.
--
-- ROLLUP MASK. A UInt16 BITMASK, matching solution/policy.yaml exactly:
--
--     platform = 1   country = 2   content_id = 4   video_type = 8
--     default_masks: 0, 1, 2, 4, 8, 3, 5, 9, 12, 15
--
-- The four dimension columns are always present; the ones NOT in the mask carry
-- a neutral value ('' or 0). Same shape as solution/sql/20_publish_boundaries.sql,
-- which is the contract the rest of the repo already implements.
--
-- An earlier draft of this file invented its own scheme --
-- Enum8('global'=0,'platform'=1,'country'=2,'video_type'=3) -- with no
-- content_id and no combination masks. That was wrong twice: it dropped six of
-- the ten documented masks, and its mask 3 meant video_type where policy.yaml's
-- mask 3 means platform+country. The same integer meaning two different things
-- in one repo is precisely the silent-wrong-answer shape this project exists to
-- avoid. Do not re-derive a mask scheme; read policy.yaml.
--
-- Only masks 0 and 15 are strictly necessary for CORRECTNESS: mask 15 is the
-- finest grain, and summing its deltas over the unwanted dimensions yields
-- exactly the coarser mask's delta stream, whose running max is the correct
-- peak. (Peaks do not sum; deltas do, and the peak comes from the deltas.) The
-- other eight are materialized purely so a common query does not pay that
-- summation. Cost at current scale is trivial -- 63,894 intervals x 2 boundaries
-- x 10 masks = 1,277,880 rows before collapse.
--
-- SORT KEY = the summing key, so it must be exactly the grain at which two
-- boundaries are the same thing. Dimensions are ordered by their bit value so
-- the key reads the same way policy.yaml does. Within any one mask the unused
-- dimensions are constant, so they cost nothing and the key behaves as
-- (mask, used dimensions, boundary_ts). Two intervals opening at the same
-- millisecond in the same slice sum to opens = 2, which is correct and is what
-- CollapsingMergeTree cannot express.
--
-- No built_at / no ingest metadata column. Any column here that is neither in
-- the sort key nor in the summed list keeps an arbitrary first-row value on
-- merge -- a trap for the next reader for no benefit.
--
-- TIMESTAMP RESOLUTION. Millisecond. Truncation is exact-losing and monotone:
-- measured peak 2,305 -> second 2,303 (-0.09%, 7.9x collapse) -> minute 2,285
-- (-0.87%) -> hour 2,213 (-3.99%). Second granularity is a defensible trade if
-- storage ever forces it; minute and hour are not. Millisecond deltas plus
-- minute checkpoints reproduce 2,305 exactly.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.concurrency_deltas
(
    policy_version  LowCardinality(String),
    clip_variant    Enum8('unclipped' = 1, 'clipped' = 2),

    rollup_mask     UInt16 COMMENT 'Bitmask: platform=1, country=2, content_id=4, video_type=8. See solution/policy.yaml rollup_mask_bits',

    -- Neutral value when the corresponding bit is NOT set in rollup_mask, so a
    -- row is self-describing and a mask filter alone never mixes grains.
    platform        LowCardinality(String) COMMENT 'Empty string when bit 1 is clear',
    country         LowCardinality(String) COMMENT 'Empty string when bit 2 is clear',
    content_id      Int64                  COMMENT '0 when bit 4 is clear. Int64: the catalogue contains a negative id',
    video_type      LowCardinality(String) COMMENT 'Empty string when bit 8 is clear',

    boundary_ts     DateTime64(3, 'UTC') COMMENT 'Half-open [start, end): a start at T raises the curve at T, an end at T lowers it at T',

    opens           UInt32,
    closes          UInt32
)
ENGINE = SummingMergeTree((opens, closes))
ORDER BY (policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, boundary_ts)
SETTINGS
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Sealed interval boundaries, ms-exact. Running sum of (opens - closes) is the concurrency curve.';

ALTER TABLE sonyliv.concurrency_deltas
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- ----------------------------------------------------------------------------
-- concurrency_bucket_net
--
-- Per-minute net, so no query ever prefix-sums from t=0.
--
-- Minute, not hour: the data is savagely skewed -- 30,177 of 63,894 boundaries
-- (47%) fall in the single hour 2026-07-26 10:00 -- so the hot hour is the
-- worst case and minute buckets cut the in-window scan 60x for the same exact
-- answer. Measured: 1,796 checkpoint rows, max 1,371 deltas in one minute.
--
-- n_deltas exists solely to keep net-zero buckets alive (see the zero-row note
-- on concurrency_deltas). It is never zero for a real bucket, so the row always
-- survives the merge. It is a correctness column, not a statistic.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.concurrency_bucket_net
(
    policy_version  LowCardinality(String),
    clip_variant    Enum8('unclipped' = 1, 'clipped' = 2),
    rollup_mask     UInt16,
    platform        LowCardinality(String),
    country         LowCardinality(String),
    content_id      Int64,
    video_type      LowCardinality(String),
    bucket          DateTime('UTC') COMMENT 'toStartOfMinute(boundary_ts)',

    opens           UInt64,
    closes          UInt64,
    n_deltas        UInt64 COMMENT 'Correctness column: keeps a net-zero bucket from being deleted on merge'
)
ENGINE = SummingMergeTree((opens, closes, n_deltas))
ORDER BY (policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, bucket)
SETTINGS
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Minute checkpoints over concurrency_deltas. Bucket NET, not level -- net is insert-commutative.';

ALTER TABLE sonyliv.concurrency_bucket_net
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- ----------------------------------------------------------------------------
-- concurrency_deltas_to_bucket_mv
--
-- This one IS legal as an incremental materialized view, and the reason is
-- worth stating because almost nothing else in this pipeline is: it is a pure
-- per-block aggregation into a commutative, associative accumulator. It never
-- needs lead/lag, never needs prior state, never retracts, never deduplicates.
-- Sums compose across blocks in any order, so block scoping costs nothing.
-- [official: query-mv-incremental -- incremental MVs are insert-block scoped]
-- ----------------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS sonyliv.concurrency_deltas_to_bucket_mv
TO sonyliv.concurrency_bucket_net
AS
SELECT
    policy_version,
    clip_variant,
    rollup_mask,
    platform,
    country,
    content_id,
    video_type,
    toStartOfMinute(boundary_ts) AS bucket,
    sum(opens)                   AS opens,
    sum(closes)                  AS closes,
    count()                      AS n_deltas
FROM sonyliv.concurrency_deltas
GROUP BY policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, bucket;


-- ----------------------------------------------------------------------------
-- concurrency_day_anchor
--
-- Absolute level at each UTC day boundary, so summing bucket nets for `base` is
-- bounded at 1,440 rows rather than growing with retained history. Without it
-- the checkpoint scheme is exact but O(hours-since-epoch), which is better than
-- O(deltas) and still not flat.
--
-- Trade-off, stated plainly: a bucket NET is insert-commutative and survives
-- late-arriving data with no recomputation. A cumulative LEVEL is not. Late
-- data landing before an anchor invalidates that anchor and every later one,
-- so anchors must be rebuilt forward from the last good one. That is why this
-- is a separate table written by the scheduled step, and not another MV.
--
-- ENGINE. ReplacingMergeTree is correct HERE, unlike in 010, and the difference
-- is worth being precise about. 010 rejects it because a session's interval SET
-- can shrink, leaving an orphan row at a start_time the new revision never
-- writes, with nothing to replace it. This table's key set never shrinks: there
-- is exactly one row per (policy, variant, mask, dim, day), forever. A
-- recomputed anchor always lands on the same key it is replacing.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.concurrency_day_anchor
(
    policy_version  LowCardinality(String),
    clip_variant    Enum8('unclipped' = 1, 'clipped' = 2),
    rollup_mask     UInt16,
    platform        LowCardinality(String),
    country         LowCardinality(String),
    content_id      Int64,
    video_type      LowCardinality(String),
    day             Date,

    level           Int64 COMMENT 'Absolute concurrency at 00:00:00.000 UTC on `day`. Signed: a negative value is a bug, not a state.',

    computed_at     DateTime64(3, 'UTC') DEFAULT now64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY (policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, day)
SETTINGS
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Absolute level at each UTC midnight. Rebuilt forward from the last good anchor when late data lands.';

ALTER TABLE sonyliv.concurrency_day_anchor
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- ============================================================================
-- PART 3 -- the scheduled step's bookkeeping
-- ============================================================================

-- ----------------------------------------------------------------------------
-- pipeline_watermark
--
-- How far each stage has consumed. Read by 011 as since_ingested_at, written
-- after a successful cycle.
--
-- The watermark is a TIMESTAMP (dirty_sessions.last_ingested_at), never
-- dirty_operation_id. That column is xxHash64(...), not a sequence -- measured
-- range 3.1e15 to 1.8e19 with 49.7% above the UInt64 midpoint -- so
-- `WHERE dirty_operation_id > {since}` selects a pseudo-random half of the
-- queue and looks like it works. This file exists partly so that mistake has
-- one obvious place not to be repeated.
--
-- Small enough that FINAL is acceptable on read -- the one place in this
-- schema where that is true, and only because the table has one row per stage.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.pipeline_watermark
(
    stage             LowCardinality(String) COMMENT 'e.g. stage01_intervals, stage02_deltas',
    policy_version    LowCardinality(String),

    watermark         DateTime64(3, 'UTC') COMMENT 'Max dirty_sessions.last_ingested_at consumed by a SUCCESSFUL cycle',
    state_revision    UInt64 COMMENT 'Cycle id of that run; matches active_intervals.state_revision',

    sessions_applied  UInt64,
    updated_at        DateTime64(3, 'UTC') DEFAULT now64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (stage, policy_version)
SETTINGS
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'One row per stage. Advance only after the cycle has committed, never before.';

ALTER TABLE sonyliv.pipeline_watermark
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- ============================================================================
-- Notes for whoever writes 021 (the read queries) and 022 (the scheduled step)
-- ============================================================================
--
-- PEAK READ. The window max is exact, and the argument is short enough to check:
-- C(t) is piecewise constant and right-continuous, changing only at delta
-- instants, so sup C over [W0,W1) is attained at W0 or immediately after some
-- transition inside it. `base` = C(W0) is exact because bucket nets are
-- associative and every earlier transition lies in exactly one earlier bucket.
-- A peak straddling W1 is base + prefix(last transition) -- a candidate here,
-- and equal to the next window's base, a candidate there. Counted twice, never
-- missed.
--
--   WITH slice AS (rollup_mask = {m:UInt16}
--                  AND platform = {pf:String} AND country = {co:String}
--                  AND content_id = {ci:Int64} AND video_type = {vt:String})
--   -- pass '' / 0 for every dimension whose bit is clear in {m}
--   WITH base AS (
--     SELECT (SELECT level FROM sonyliv.concurrency_day_anchor FINAL
--              WHERE <slice> AND day = toDate({w0:DateTime64(3)}))
--            + sum(opens) - sum(closes) AS lvl
--     FROM sonyliv.concurrency_bucket_net
--     WHERE policy_version = {p:String} AND clip_variant = {v:String} AND <slice>
--       AND bucket >= toStartOfDay({w0:DateTime64(3)}) AND bucket < {w0:DateTime64(3)}
--   ),
--   inner_prefix AS (
--     SELECT sum(sum(opens) - sum(closes))
--              OVER (ORDER BY boundary_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS pfx
--     FROM sonyliv.concurrency_deltas
--     WHERE policy_version = {p:String} AND clip_variant = {v:String} AND <slice>
--       AND boundary_ts >= {w0:DateTime64(3)} AND boundary_ts < {w1:DateTime64(3)}
--     GROUP BY boundary_ts
--   )
--   SELECT greatest((SELECT lvl FROM base),
--                   (SELECT lvl FROM base) + (SELECT max(pfx) FROM inner_prefix)) AS peak;
--
-- An UNMATERIALIZED mask (6, 7, 10, 11, 13, 14) is served by the same query
-- against rollup_mask = 15 with the unwanted dimensions dropped from the
-- GROUP BY -- the summed deltas are exactly that mask's delta stream, and the
-- running max over them is its exact peak. Never sum the coarser masks'
-- *peaks*; those genuinely do not compose.
--
-- Two things in that query are load-bearing and look optional:
--   * GROUP BY boundary_ts BEFORE the running sum is what implements stop-wins
--     at the same millisecond. It is the difference between 2,305 exactly and
--     approximately right.
--   * greatest(base, ...) covers a window whose every transition is negative:
--     it peaks at W0, where there is no transition to be the argmax.
--
-- CONTENT DRILL-DOWN is now served by masks 4, 5, 12 and 15, per policy.yaml --
-- it is no longer pushed onto the interval table. The scale caveat still stands
-- and should be revisited before running at 1B events/day: the content-grained
-- masks are projected at 136.8M rows/day and SummingMergeTree collapses them
-- ~1.00x at any density, so they cost full price. At the current 1.3M rows the
-- trade is not worth making, and correctness against an unknown benchmark query
-- set beats a storage optimisation. If it ever has to give, drop masks 5 and 12
-- (derivable from 15) before dropping 4.
--
-- The paragraph below applies to any query that does reach for the interval
-- table directly -- note that active_intervals
-- is ORDER BY (policy_version, clip_variant, session_key, start_time), so
-- start_time sits behind session_key's 10,866 distinct values and a range
-- predicate prunes nothing. Measured analogue on events_clean: a 1-hour
-- event_ts predicate matched 342,328 rows but READ 845,415 of 901,348 (93.8%),
-- against 8,202 (0.9%) for a leading-column lookup. Either add a time-ordered
-- day-partitioned copy, or split intervals at 15-minute boundaries (measured
-- 1.209x row inflation, 38,621 from 31,947) so the lookback bound is a schema
-- invariant rather than a property of today's data. Do not rely on a measured
-- max duration: 7 intervals already exceed 60 minutes (max 73.77), a 60-minute
-- lookback silently returns 2,304 instead of 2,305, and nothing in the schema
-- stops tomorrow's data from being worse.
--
-- REBUILD. Never re-INSERT into these Summing tables -- re-inserting adds, and
-- the only thing between a rebuild and a doubled count is an insert-dedup
-- window that expires on a timer. Rebuild into a shadow table and
-- EXCHANGE TABLES (usable here: database sonyliv has engine = Shared, and
-- Keeper dedup state is UUID-keyed so it follows the table, not the name).
-- The swap alone is NOT sufficient: it discards every delta the live path wrote
-- during the rebuild, projected 67,000-475,000 at 792 transitions/s. Quiesce
-- the writer, or record a watermark and replay the gap after the swap. Pick one
-- explicitly.
--
-- NOT USED ANYWHERE, ON PURPOSE. No refreshable materialized view: its APPEND
-- is silently deduplicated (measured 33.7% of legitimate appends dropped in the
-- hot 90 minutes at the global grain, with no exception and written_rows still
-- reporting success), and it cannot escape that from the inside because
-- `SETTINGS insert_deduplication_token = toString(now())` does not parse --
-- settings take literals only, so a refreshable MV can carry a constant token,
-- which is strictly worse than none. No projection. No FINAL in any serving
-- path except pipeline_watermark. No DEPENDS ON chain. No CollapsingMergeTree.
