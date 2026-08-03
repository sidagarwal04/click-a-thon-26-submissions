-- =============================================================================
-- 020_projections.sql — projections for sonyliv_prod, and the engine constraint
--                        that rules most of the schema out
--
-- Measured on the live service (ClickHouse 26.2.1.525, aws ap-south-1,
-- 2 replicas) on 2026-08-02. There are currently ZERO projections defined
-- anywhere on this service, so everything below starts from a clean baseline.
--
-- READ THIS FIRST — the constraint that decides most of the answer.
--
--   SELECT hostName(), name, value, default, changed
--   FROM clusterAllReplicas(default, system.merge_tree_settings)
--   WHERE name = 'deduplicate_merge_projection_mode';
--
--     c-salmonaws-ak-30-server-2gi3lh9-0 | throw | throw | 0
--     c-salmonaws-ak-30-server-l6u3rgu-0 | throw | throw | 0
--
-- The in-server description reads: "Whether to allow create projection for the
-- table with non-classic MergeTree, that is not (Replicated, Shared) MergeTree.
-- Ignore option is purely for compatibility which might result in incorrect
-- answer. Otherwise, if allowed, what is the action when merge projections,
-- either drop or rebuild. So classic MergeTree would ignore this setting."
--
-- Plain SharedMergeTree is "classic" and ignores it. SharedReplacingMergeTree,
-- SharedSummingMergeTree and SharedAggregatingMergeTree are NOT, so
-- ADD PROJECTION on them THROWS at default settings.
--
-- Measured split for sonyliv_prod — 9 of 16 MergeTree tables are ineligible:
--
--   BLOCKED (non-classic)                         rows        engine
--     events_clean                            9,000,048   SharedReplacingMergeTree
--     fleet_sessions                            452,304   SharedReplacingMergeTree
--     fleet_sessions_cleared                    327,206   SharedReplacingMergeTree
--     serving_concurrency_live                  149,097   SharedReplacingMergeTree
--     concurrency_minute                        108,927   SharedSummingMergeTree
--     session_intervals                          89,594   SharedReplacingMergeTree
--     content_dim                                33,464   SharedReplacingMergeTree
--     concurrency_watermark / serving_watermark       <5   SharedReplacingMergeTree
--
--   ELIGIBLE (classic SharedMergeTree)
--     events_raw                              9,023,668
--     dirty_sessions                          5,739,016
--     serving_concurrency_minute                483,499
--     ingest_batches                             22,371
--     serving_watermark_history                   3,044
--     ingest_rejects / serving_concurrency_minute_staging   0
--
-- So the answer to "can projections speed up the big wide table" is: NOT
-- events_clean, not without changing the mode per table, and each escape has a
-- price — 'drop' discards the projection on merge, 'rebuild' pays to rebuild it
-- on every merge, and 'ignore' is documented as possibly producing an INCORRECT
-- ANSWER. On a scoring problem where a wrong number costs the same as a crash,
-- 'ignore' is not on the table.
--
-- events_clean is doubly excluded: the official mergetree page states plainly
-- that "projections are not supported in the SELECT statements with the FINAL
-- modifier", and the serving views read it through FINAL. Fix the FINAL first
-- (see 010_read_path_rewrites.sql R5), then revisit.
--
-- ALSO NOT AVAILABLE HERE, despite what the docs page says:
--   WHERE clauses inside projection definitions are a 26.7 feature (changelog
--   #102347). clickhouse.com/docs/sql-reference/statements/alter/projection
--   documents them because the site publishes latest, and
--   clickhouse.com/docs/data-modeling/projections simultaneously lists "No
--   WHERE clauses in projection definitions" as a limitation. The two pages
--   contradict each other. On 26.2 it is a parser error. Do not design
--   partial/filtered projections against that page.
--
-- HOW TO APPLY. ADD PROJECTION is metadata-only and lazy: it affects only newly
-- inserted parts. Existing data is not covered until MATERIALIZE PROJECTION,
-- which is a MUTATION. Run the materialize during a quiet window; it rewrites
-- parts and competes with ingest.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- P1. dirty_sessions — the single clearest win in the schema
--
-- TARGET QUERY (normalized_query_hash 922453489504088000), the #1 SELECT by
-- bytes read on any projection-eligible table:
--
--   SELECT DISTINCT session_key FROM sonyliv_prod.dirty_sessions
--   WHERE last_ingested_at > {watermark} LIMIT 50000
--
-- MEASURED over 2026-08-01 22:23:46 -> 2026-08-02 00:17:22:
--   846 executions, 595,779,224 rows read, 7.87 GiB, 11,068 ms total.
--   A single execution I ran on 2026-08-02: 761,874 rows / 12,189,984 bytes
--   to return 50,000 keys — 15:1 read amplification, 846 times over.
--
-- WHY THE INDEX CANNOT HELP TODAY. This is definitional, not speculative:
--   ORDER BY (session_start_date, session_key, last_ingested_at, ingest_batch_id)
--   PARTITION BY  <none>
-- The query constrains only last_ingested_at — the THIRD key column — with
-- nothing pinning session_start_date or session_key. A primary index prunes on
-- a PREFIX. There is no prefix here, so it scans.
--
-- WHY NOT THE CHEAPER SKIP INDEX. A minmax on last_ingested_at was the obvious
-- cheaper alternative and I tested the assumption it rests on. Measured:
--   a 1-minute last_ingested_at window holds 911,161 rows and spans exactly
--   1 of the 9 distinct session_start_date values.
-- So one minute of ingest lands inside a single date block and is then spread
-- across that entire block in session_key order — a session is re-dirtied many
-- times over the run, so consecutive granules each span a wide last_ingested_at
-- range. Granule-level minmax would prune almost nothing. Rejected.
--
-- WHY NOT REORDER THE TABLE. session_start_date/session_key is the lookup path
-- the recompaction join depends on. Reordering would fix this query and break
-- that one. A projection gives both orders. This is exactly the case
-- projections exist for.

ALTER TABLE sonyliv_prod.dirty_sessions
    ADD PROJECTION IF NOT EXISTS proj_dirty_by_last_ingested
    (
        SELECT session_key, last_ingested_at
        ORDER BY last_ingested_at
    );

-- Mutation. Run in a quiet window.
ALTER TABLE sonyliv_prod.dirty_sessions
    MATERIALIZE PROJECTION proj_dirty_by_last_ingested
    SETTINGS mutations_sync = 1;

-- Storage cost, bounded: two columns (UInt64 + DateTime64(3)) against a
-- 9-column base table plus a MATERIALIZED xxHash64. The projection is narrow
-- by design — it carries only what the target query selects and filters on.


-- -----------------------------------------------------------------------------
-- P2. events_raw — the ingestion-monitoring dashboard scans the whole table
--
-- TARGET QUERIES — four shapes, all filtering and grouping on _ingested_at,
-- none of which can use the index. MEASURED in the same window:
--
--   hash 10063755899576281000  26 execs  50,656,994 rows  498.11 MiB
--     SELECT toStartOfInterval(toDateTime(_ingested_at), INTERVAL 60 second) AS ts,
--            quantile(0.50)(dateDiff('millisecond', event_timestamp, _ingested_at))/1000, ...
--     WHERE _ingested_at >= ...
--
--   hash 10965201738222256000  25 execs  50,505,301 rows  399.60 MiB
--     SELECT toStartOfInterval(toDateTime(_ingested_at), INTERVAL 60 second) AS ts,
--            _source_file AS producer, count()/60 AS rows_per_second
--     WHERE _ingested_at >= ...
--
--   plus two _CAST-spelled siblings: 10 execs 379.93 MiB, 11 execs 249.01 MiB.
--   Together ~72 executions and ~1.49 GiB in under two hours, growing linearly
--   with the table forever.
--
-- WHY THE INDEX CANNOT HELP TODAY:
--   ORDER BY (video_session_id, event_timestamp)
--   PARTITION BY toYYYYMM(event_timestamp)
-- _ingested_at appears in NEITHER. It is a real column (position 16), not a
-- virtual one, so it is projectable — but the table is organised by session and
-- by EVENT time, while these queries filter on INGEST time. Those two clocks
-- diverge precisely when ingestion lags, which is the only time anyone looks at
-- this dashboard.
--
-- The projection carries the three columns the four queries need. event_timestamp
-- is included because the lag metric is dateDiff(event_timestamp, _ingested_at)
-- and without it the projection cannot serve query 1.

ALTER TABLE sonyliv_prod.events_raw
    ADD PROJECTION IF NOT EXISTS proj_raw_by_ingested_at
    (
        SELECT _ingested_at, _source_file, event_timestamp
        ORDER BY _ingested_at
    );

ALTER TABLE sonyliv_prod.events_raw
    MATERIALIZE PROJECTION proj_raw_by_ingested_at
    SETTINGS mutations_sync = 1;


-- -----------------------------------------------------------------------------
-- REJECTED, with reasons. Recorded so nobody re-proposes them.
--
-- serving_concurrency_minute — REJECTED, already optimal.
--   ORDER BY (dim_mask, minute_start, platform, video_type, category,
--             app_version, content_id)
--   PARTITION BY toYYYYMMDD(minute_start)
--   The dashboard tier filters on dim_mask and minute_start, which IS the sort
--   key prefix, inside a daily partition. It is 483,499 rows in 8 parts / 4.68
--   MiB. There is nothing to reclaim. Adding a projection here would cost
--   storage and merge CPU for no gain.
--
-- events_clean — BLOCKED twice over. SharedReplacingMergeTree, so ADD PROJECTION
--   throws at deduplicate_merge_projection_mode = 'throw'; and the hot readers
--   use FINAL, which cannot use a projection even if one existed. The real win
--   on this table is not a projection at all — it is R1 in
--   010_read_path_rewrites.sql, which removes events_dedup from the hot path
--   for a MEASURED 10.2x on the single most expensive SELECT in the workload.
--   Do that first; it is free and it is already proven.
--
-- session_intervals / serving_concurrency_live / concurrency_minute — BLOCKED,
--   non-classic engines. Fix the FINAL usage (R5) before considering whether
--   changing the mode is worth it.
--
-- _part_offset "filter projections" — NOT APPLICABLE at current settings.
--   Available in 26.2 (both the 25.6 form `SELECT _part_offset ORDER BY col`
--   and the 26.1 compact form `INDEX col TYPE basic`), but gated by
--   min_table_rows_to_use_projection_index and
--   max_projection_rows_to_use_projection_index, both measured at 1,000,000 on
--   this service. They are the right tool for point-lookup-by-secondary-key,
--   which is not the shape of any query in this workload — every offender is a
--   RANGE scan on a timestamp, which a normal sorted projection serves better.


-- =============================================================================
-- VERIFICATION — run after MATERIALIZE. A projection that is silently not used
-- is the worst outcome: you pay the storage and the merge cost and get nothing.
-- =============================================================================

-- V1. The projection exists and has parts on BOTH replicas. Per-replica, because
--     this schema has already been bitten once by per-replica divergence.
SELECT hostName() AS host, database, table, name, parts, rows, formatReadableSize(bytes_on_disk) AS sz
FROM
(
    SELECT hostName() AS h, database, table, name, count() AS parts, sum(rows) AS rows,
           sum(bytes_on_disk) AS bytes_on_disk
    FROM clusterAllReplicas(default, system.projection_parts)
    WHERE active AND database = 'sonyliv_prod'
    GROUP BY h, database, table, name
);

-- V2. The optimizer actually picks it. Must name the projection in the plan.
EXPLAIN projections = 1
SELECT DISTINCT session_key
FROM sonyliv_prod.dirty_sessions
WHERE last_ingested_at > toDateTime64('2026-08-01 23:22:23.275', 3, 'UTC')
LIMIT 50000;

-- V3. Reference-free correctness: the projection must not change the answer.
--     force_optimize_projection = 0 vs 1 must agree exactly. This is the check
--     that matters — a projection that is merely slow is an annoyance, one that
--     returns a different number is the failure mode this repo exists to avoid.
SELECT
    (SELECT count() FROM (SELECT DISTINCT session_key FROM sonyliv_prod.dirty_sessions
       WHERE last_ingested_at > {watermark:DateTime64(3,'UTC')})
     SETTINGS optimize_use_projections = 0) AS without_projection,
    (SELECT count() FROM (SELECT DISTINCT session_key FROM sonyliv_prod.dirty_sessions
       WHERE last_ingested_at > {watermark:DateTime64(3,'UTC')})
     SETTINGS optimize_use_projections = 1) AS with_projection,
    throwIf(without_projection != with_projection,
            'PROJECTION CHANGES THE ANSWER. Drop it immediately: '
            'ALTER TABLE sonyliv_prod.dirty_sessions DROP PROJECTION proj_dirty_by_last_ingested') AS ok;

-- V4. It was worth it. Compare read_bytes before and after in query_log for the
--     same normalized_query_hash. If bytes did not fall, the projection is not
--     being used and V2 lied to you.
SELECT
    normalized_query_hash AS h,
    countIf(event_time <  {applied_at:DateTime}) AS execs_before,
    countIf(event_time >= {applied_at:DateTime}) AS execs_after,
    round(avgIf(read_bytes, event_time <  {applied_at:DateTime})) AS bytes_before,
    round(avgIf(read_bytes, event_time >= {applied_at:DateTime})) AS bytes_after,
    round(avgIf(read_bytes, event_time <  {applied_at:DateTime})
        / nullIf(avgIf(read_bytes, event_time >= {applied_at:DateTime}), 0), 2) AS speedup
FROM clusterAllReplicas(default, system.query_log)
WHERE type = 'QueryFinish'
  AND normalized_query_hash IN (922453489504088000, 10063755899576281000, 10965201738222256000)
GROUP BY h;
