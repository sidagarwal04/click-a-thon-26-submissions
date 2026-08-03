-- ============================================================================
-- Stage 01 target: normalized active viewing intervals.
--
-- One row per stretch of genuinely active viewing, per session, per clip
-- variant. This is the only thing stages 02+ read; nothing downstream touches
-- events_clean or events_raw again.
--
-- Apply with:
--   clickhouse-client --multiquery < pipeline/sql/010_active_intervals.sql
--
-- Idempotent and converging: CREATE TABLE IF NOT EXISTS is a no-op against an
-- existing table, so the settings corrections are re-issued as ALTER ... MODIFY
-- SETTING (metadata-only). A table created by an earlier version of this file
-- is fixed by running it again rather than rebuilt. Same pattern as
-- ingest/sql/002_events_raw.sql.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- active_intervals
--
-- SORT KEY. Exactly three readers touch this table, and the key serves them:
--
--   1. active_intervals_current  GROUP BY policy_version, clip_variant, session_key
--                                -- every downstream read goes through this
--   2. stage 02 (deltas)         reads a whole policy+variant slice
--   3. correction lane           WHERE session_key IN (...)
--
--   policy_version   1 value today; 2-3 if we publish side-by-side answers under
--                    contested semantics, as COMPARISON.md commits to. Prunes
--                    nothing right now -- but ORDER BY is immutable, so it is
--                    either here or never. A thin bet, taken deliberately.
--   clip_variant     2 values. Every reader picks exactly one, so this genuinely
--                    halves the scan.
--   session_key      108,486 values on the unseen day. The correction lane's
--                    lookup key -- and, measurably, the ONLY thing in this key
--                    that earns its position. See below.
--   start_time       Highest cardinality, last. Also leaves stage 02's output
--                    pre-sorted.
--
-- ----------------------------------------------------------------------------
-- WHY THIS KEY, RE-DERIVED 2026-08-02 AT UNSEEN-DAY SCALE
-- ----------------------------------------------------------------------------
-- This block used to claim the key existed so the resolution view's GROUP BY
-- could "stream instead of re-sorting", and called that "the main reason this
-- key looks the way it does". THAT CLAIM IS FALSE and is struck. Measured:
--
--   * optimize_aggregation_in_order defaults to 0, so in-order aggregation is
--     never used on that read by default, on ANY candidate key.
--   * Forced on, it is 2.4x-3.6x SLOWER than the default parallel hash
--     aggregation (inner GROUP BY 16.8 ms -> 40.4 ms).
--   * Every non-prefix candidate still reported AggregatingInOrderTransform
--     anyway, because ClickHouse streams on the (policy_version, clip_variant)
--     common prefix regardless of what follows.
--   * No candidate introduced a Sorting step.
--
-- The key survives on a different and real argument: THE CORRECTION LANE.
-- session_key ahead of start_time is the only choice any candidate changes that
-- matters. Granules read for `WHERE session_key IN (...)`, 630,000-row table:
--
--     4 keys      baseline 4/77     start_time-leading 39/77     9.75x
--     29 keys     baseline 28/770   start_time-leading 385/770  13.75x   (10x scale)
--     204 keys    baseline 169/770  start_time-leading 385/770   2.28x   (10x scale)
--
-- Honest limit on that argument: at 1x scale the advantage is gone by ~236 keys
-- (both 39/77). It rests on the correction lane being a handful of dirty
-- sessions, and on the table growing. Both hold here.
--
-- Rejected, each measured rather than argued:
--
--   (clip_variant, policy_version, session_key, start_time)
--       A pure no-op. 30-byte storage delta and identical granule counts on
--       every reader. Both leading columns are pinned equality predicates, so
--       their relative order is invisible to KeyCondition.
--
--   (policy_version, clip_variant, start_time, session_key)
--       Best storage on the axis -- -12.85% at 1x, -22.53% at 10x -- and
--       rejected anyway. It NEVER prunes session_key: 39/77 at every key-set
--       size from 1 to 1,030 keys. It buys a 2.17x win on a time-window read
--       that the contract flags UNSUPPORTED, and only for morning windows
--       (1.05x late, 1.00x full-day). The storage win is recoverable on the
--       codec axis instead, which is where it has been taken.
--
--   (policy_version, clip_variant, session_start_date, session_key, start_time)
--       Strictly dominated. Storage -0.26% (noise), and R3 actively worse
--       (6/77 vs 4/77 at 4 keys) because session_start_date is 99% one value
--       and just pushes session_key a position deeper.
-- ----------------------------------------------------------------------------
--
-- session_start_date is deliberately NOT here, though an earlier draft had it
-- between clip_variant and session_key. It serves no reader: stage 02 needs
-- intervals that OVERLAP a service day (a start_time/end_time range), not ones
-- whose session happened to start that day -- a 43-hour session starting on the
-- 24th still contributes to the 26th. And sitting mid-key it broke the view's
-- GROUP BY prefix, taxing the one read everything depends on.
--
-- Scale honesty, restated for the unseen day. The tuning extract was 31,947
-- intervals x 2 variants = 63,894 rows, about eight granules, and the old note
-- here reasonably said no sort key prunes meaningfully across eight granules.
-- That is no longer the situation: 108,486 sessions at ~2.9 intervals each
-- gives roughly 630,000 rows, about 77 granules, and the correction lane's
-- 4/77 vs 39/77 is a real 9.75x rather than a rounding difference.
--
-- The old note also justified the key by "the aggregation-in-order property
-- above". That property was measured and does not exist -- see the struck claim
-- above. The key is justified by the correction lane, and by nothing else.
--
-- ----------------------------------------------------------------------------
-- NOT PARTITIONED, and this is now a measured decision rather than a size one.
-- ----------------------------------------------------------------------------
-- Re-evaluated 2026-08-02 when the rest of the schema moved from monthly to
-- DAILY partitions. active_intervals must NOT follow, and the reason is not
-- taste.
--
-- IT WOULD NOT LOAD. The real data spans 189 distinct dates. Both replicas
-- report max_partitions_per_insert_block = 100 and
-- throw_on_max_partitions_per_insert_block = 1, unchanged defaults -- verified
-- on the service. 011 builds this table with a SINGLE
-- `INSERT INTO active_intervals ... SELECT`, so 189 daily partitions makes that
-- one statement throw Code: 252 TOO_MANY_PARTS. The build would simply fail.
--
-- It also costs on every reader that is correct. Granules read, measured:
--
--     partitioning              R1/R2 slice      correction lane
--     none (this)               39/77            4/77
--     daily, 48 dates           86/77 (2.21x)    98/77  (24.5x)
--     daily, 189 dates          227    (5.82x)          (95x)
--     monthly, 7 partitions     45/77 (1.15x)    8/77   (4.0x)
--
-- Storage is a wash in every variant (+0.42% / -0.24%, both noise).
--
-- AND IT BUYS NOTHING, because of what these rows ARE. An interval has a
-- DURATION and straddles the boundary. The correct time-window read is
-- `start_time < W1 AND end_time > W0`, and `end_time > W0` can never prune a
-- start-date partition key -- confirmed against all four variants, which read
-- the same granules partitioned or not. The only query daily partitioning
-- accelerates is `WHERE session_start_date = 'D'`, which is the WRONG query:
-- measured on the fixture it returned 0 of 5,344 intervals for one window.
--
-- On this data 105 sessions (0.097%) genuinely cross a day boundary, 7 span
-- more than two days, and one runs to 2026-08-03 -- so the trap is live, not
-- theoretical.
--
-- Do NOT adopt daily here merely because events_raw, ingest_batches,
-- ingest_rejects and concurrency_minute_versions did. Those hold zero-duration
-- POINT events and are append-and-drop, where DROP PARTITION is the retention
-- mechanism. This table holds durations and is rebuilt wholesale.
--
-- If a DROP PARTITION lifecycle is ever genuinely needed, use MONTHLY: 7
-- partitions, 1.15x on the mandatory path, and safely under
-- max_partitions_per_insert_block. Nothing in the current design needs it.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sonyliv.active_intervals
(
    policy_version      LowCardinality(String) COMMENT 'Semantic contract that produced this row; see solution/policy.yaml',

    -- 'unclipped': an open session runs to last_eligible_signal + timeout, which
    --              can land after the last event we ever observed.
    -- 'clipped':   the same interval, truncated at the observation horizon.
    -- Both are built every run. Which one is authoritative is a judgement call
    -- against a private answer key, so the pipeline refuses to make it silently.
    clip_variant        Enum8('unclipped' = 1, 'clipped' = 2),

    -- Retained as a plain column, not a sort-key column. Useful for eyeballing
    -- and for joining back to dirty_sessions, but it prunes nothing that matters
    -- here -- see the sort-key note above for why it was taken out of the key.
    session_start_date  Date,

    session_key         UInt64 COMMENT 'Joins to events_clean.session_key and dirty_sessions.session_key',
    user_key            UInt64 COMMENT 'Canonical user, anchored on the first VideoSessionStart',

    -- Presentation ordering ONLY. Never a join key, never an identity.
    -- row_number() is positional: a late event that inserts an interval in the
    -- middle of a session renumbers every interval after it. Corrections diff
    -- boundary timestamps, which do not shift. Joining on this would report
    -- three intervals changed when one was added.
    -- Measured: max 167 intervals in one session, p99 11, mean 2.94. UInt16
    -- leaves room; UInt8 would be 1.5x headroom against a 255 ceiling.
    interval_index      UInt16,

    -- CODEC(T64, ZSTD(1)) on both. Verified end to end by building THIS file's
    -- CREATE TABLE at 630,000 rows and diffing it against the same DDL with the
    -- CODEC clauses stripped -- so these are the shipped statement's numbers,
    -- not a paraphrase of it:
    --
    --   start_time      3,345,855 -> 2,146,909 B  (0.642x)
    --   end_time        3,405,030 -> 2,210,677 B  (0.649x)
    --   state_revision     22,768 ->     5,316 B  (0.233x, and see below)
    --   every other column               unchanged, ratio 1.000
    --   WHOLE TABLE    13,949,483 -> 11,538,732 B (-17.3%)
    --
    -- Deliberately NOT DoubleDelta, even though ingest/sql/002_events_raw.sql
    -- uses it on its timestamps. Copying that here is measurably WORSE:
    -- 1.099x on start_time (+242,564 B) and 1.137x on end_time. DoubleDelta
    -- wins on events_raw because event_timestamp is the second sort-key column
    -- and is therefore ascending WITHIN a session. Here start_time is the
    -- FOURTH column, behind a 108,486-value session_key, so consecutive rows
    -- jump between unrelated sessions and the second difference is noise.
    -- end_time is not sorted at all.
    --
    -- THESE CODECS ARE COUPLED TO THE SORT KEY ABOVE. The ranking is not a
    -- property of the data alone -- it INVERTS under a start_time-leading key,
    -- where Delta+ZSTD becomes 0.827x and T64 becomes 1.098x. If the ORDER BY
    -- is ever revisited, re-measure these two columns rather than carrying the
    -- choice across. That coupling is also why the -12.85% storage win the
    -- start_time-leading key offered is not simply additive with this.
    start_time          DateTime64(3, 'UTC') COMMENT 'Inclusive. Half-open interval [start_time, end_time)' CODEC(T64, ZSTD(1)),
    end_time            DateTime64(3, 'UTC') COMMENT 'Exclusive' CODEC(T64, ZSTD(1)),

    -- Int64, not Int32, deliberately. The catalogue spans -987,654,322 to
    -- 2,078,179,327 and Int32 tops out at 2,147,483,647 -- it fits today with
    -- 3.2% headroom, which is too thin for a catalogue that grows.
    content_id          Int64,

    platform            LowCardinality(String),   -- 10 distinct
    country             LowCardinality(String),   -- 1 distinct in the extract, retained for unseen-day correctness
    video_type          LowCardinality(String),   -- resolved from content_dict at build time

    -- Append-only revision history. A rebuild of one session writes a higher
    -- revision rather than mutating; readers resolve to the winning revision.
    -- Read through active_intervals_current, never this table directly.
    --
    -- CODEC(T64, ZSTD(1)) here is a DEFECT FIX, not a micro-optimisation.
    -- ZSTD(1) -- ClickHouse Cloud's default codec, verified as
    -- system.parts.default_compression_codec on events_raw and events_clean --
    -- is pathological on a constant small integer in a wide column. Measured
    -- independently, 630,000 rows of a constant UInt64 = 1:
    --
    --     ZSTD(1)  (Cloud default)   162,042 B
    --     LZ4                         22,768 B
    --     T64 + ZSTD(1)                5,316 B      <- 30.5x smaller
    --     ZSTD(3)                      3,927 B
    --
    -- Reproducible, and value-dependent: constants 1, 2, 255 and 256 trigger it;
    -- 1.78e12 and UINT64_MAX do not; ZSTD(2) triggers it, ZSTD(3) does not.
    -- state_revision is this schema's only always-constant integer column, so
    -- untreated it silently becomes one of the largest columns in the table
    -- while holding a single repeated value.
    --
    -- NOTE when re-measuring locally: chdb's default codec is LZ4, Cloud's is
    -- ZSTD(1). A chdb A/B therefore shows only 22,768 -> 5,316 (4.3x) and
    -- UNDERSTATES this by 7x. The number that matters is the Cloud one.
    state_revision      UInt64 CODEC(T64, ZSTD(1)),

    built_at            DateTime64(3, 'UTC') DEFAULT now64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (policy_version, clip_variant, session_key, start_time)
SETTINGS
    -- Without these, a re-run of stage 01 is a no-op for exactly one hour and
    -- then silently doubles the table. ClickHouse Cloud substitutes
    -- SharedMergeTree for MergeTree, which reads the *replicated* window and
    -- expires it after replicated_deduplication_window_seconds -- server default
    -- 3600. The non-replicated window has no time component at all, so a laptop
    -- would never reveal this. Matches ingest/sql/002_events_raw.sql, which had
    -- to be corrected for the same reason.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000;


-- CREATE TABLE IF NOT EXISTS does nothing to a table that already exists, so a
-- database built by an earlier version of this file would keep the server
-- defaults forever and the correction would never arrive. Converge explicitly.
ALTER TABLE sonyliv.active_intervals
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- ----------------------------------------------------------------------------
-- proj_session_revision -- kills the full scan inside active_intervals_current
--
-- MEASURED PROBLEM. The view below resolves the winning revision with an
-- `IN (SELECT ... GROUP BY ...)` subquery. A normal view is inlined, so the
-- caller's predicate pushes into the OUTER scan -- but there is no mechanism
-- that pushes it into the IN-subquery, which therefore scans the WHOLE table on
-- every read. Measured on the service, the canonical read
-- (policy_version + clip_variant pinned, returning 31,947 intervals):
--
--     via active_intervals_current   96,662 rows / 2,264,336 bytes
--     prefix-bounded floor           32,768 rows / 1,114,178 bytes
--                                    ------------------------------
--                                    2.95x rows, 2.03x bytes overhead
--
-- 96,662 = 63,894 (unprunable inner GROUP BY) + 32,768 (pruned outer). This is
-- the mandatory read path for every downstream stage, and the overhead is
-- structural: it grows with the table and no predicate reduces it.
--
-- WHY A PROJECTION AND NOT A REWRITE. Two rewrites were measured and rejected:
--
--   * Single-pass window -- replacing the IN-subquery with
--     `max(state_revision) OVER (PARTITION BY policy_version, clip_variant,
--     session_key)` reads 63,894 instead of 96,662, but NOT the 32,768 floor.
--     ClickHouse 26.2 does not push a filter through a Window step even when
--     every predicate column is in the PARTITION BY. Verified with
--     EXPLAIN indexes = 1: `Condition: true`, `Granules: 8/8`, and the Filter
--     node sits above the Window. It also adds a full Sorting step.
--
--   * Parameterized view -- reaches the floor, but changes the call syntax to
--     active_intervals_current(policy_version = ...), which breaks every
--     existing caller and docs/TABLE-CONTRACT.md along with them.
--
-- An aggregate projection whose body is EXACTLY the inner subquery is served
-- instead of the base table, is additive, and needs no caller to change.
--
-- ELIGIBILITY. active_intervals is a plain (Shared)MergeTree -- "classic" in the
-- sense deduplicate_merge_projection_mode means. That setting is `throw` on both
-- replicas (default, unchanged), which blocks ADD PROJECTION on the
-- Replacing/Summing/Aggregating tables in this schema but NOT on this one. Of
-- the 13 MergeTree tables in `sonyliv`, 6 are eligible (active_intervals,
-- concurrency_minute_versions, events_raw, dirty_sessions, ingest_batches,
-- ingest_rejects) and 7 are blocked.
--
-- PROVEN, not assumed. Against the real DDL and row shape (63,894 rows /
-- 10,866 sessions x 2 variants), the isolated inner subquery goes from
--     ReadFromMergeTree (active_intervals)      Granules 8/8
-- to
--     ReadFromMergeTree (proj_session_revision) Granules 3/8
-- and `force_optimize_projection = 1` accepts it. Control: an unrelated
-- aggregate under the same setting throws PROJECTION_NOT_USED, so the signal
-- discriminates rather than passing everything. Projection size 85.11 KiB
-- against a 915 KiB table -- it holds one row per (policy, variant, session),
-- so it grows with SESSIONS, not with intervals.
--
-- Engine eligibility on SharedMergeTree specifically can only be confirmed by
-- running the ALTER; V-checks in 041 assert it landed rather than assuming.
-- ----------------------------------------------------------------------------

-- RE-MEASURED at 630,000 rows (unseen-day scale), and it still pays:
--   inner revision scan   630,000 -> 216,972 rows   (2.90x), granules 77 -> 27
--   full resolution read  949,488 -> 536,460 rows   (1.77x)
--   cost                  +11.7% storage
--
-- NOTHING ELSE IS ADDED TO THIS TABLE, and that is a measured result too:
--
--   * minmax skip index on start_time, on end_time, and on the pair -- at
--     GRANULARITY 1, 4 and 16. All SIX configurations prune EXACTLY ZERO
--     granules (77/77, bit-identical to no index). Under session_key ordering
--     every granule spans nearly the whole time range: the average granule
--     covers 185.59 of the 186.95 available days, so every minmax range matches
--     every predicate. The indexes were proven live by an impossible-range
--     control that does prune 77/77 -> 0/77 -- they work, they just cannot help
--     here.
--
--   * a normal projection ORDER BY (start_time, end_time) to serve time-window
--     reads. 2.14x at the 10:00 hot hour, decaying to 1.13x at 20:00 and 1.00x
--     at 23:00 where the optimizer declines it outright, for +62.8% storage.
--     Rejected: it pays only where the data happens to be dense today.
--
-- Time-window reads stay served by concurrency_deltas + concurrency_bucket_net
-- + concurrency_day_anchor, which is already what docs/TABLE-CONTRACT.md says.
ALTER TABLE sonyliv.active_intervals
    ADD PROJECTION IF NOT EXISTS proj_session_revision
    (
        SELECT policy_version, clip_variant, session_key, max(state_revision)
        GROUP BY policy_version, clip_variant, session_key
    );

-- Existing parts do not carry a newly added projection until materialized. This
-- is a mutation: it is idempotent but not free, so it is safe to re-run and
-- wasteful to re-run needlessly.
ALTER TABLE sonyliv.active_intervals
    MATERIALIZE PROJECTION proj_session_revision;


-- ----------------------------------------------------------------------------
-- active_intervals_current
--
-- READ THIS, NOT active_intervals.
--
-- The base table keeps every revision of every session. Resolving to the
-- winning revision is not optional -- a query that forgets counts a session's
-- intervals once per rebuild. Making it a view means downstream code cannot
-- forget, which is the same reason events_dedup exists over events_clean.
--
-- Why not ReplacingMergeTree, which is the usual answer for this shape: it
-- replaces rows sharing a sort key, but a session's interval *set* can shrink.
-- A late pause that removes an interval leaves an orphan row at a start_time
-- the new revision never writes, so nothing replaces it. Only whole-set
-- resolution by revision is correct here.
--
-- The IN-subquery below is written to match proj_session_revision above
-- EXACTLY. If you change its GROUP BY keys or its aggregate, the projection
-- silently stops matching and this view goes back to a full scan with no error.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW sonyliv.active_intervals_current AS
SELECT *
FROM sonyliv.active_intervals
WHERE (policy_version, clip_variant, session_key, state_revision) IN
(
    SELECT
        policy_version,
        clip_variant,
        session_key,
        max(state_revision)
    FROM sonyliv.active_intervals
    GROUP BY policy_version, clip_variant, session_key
);
