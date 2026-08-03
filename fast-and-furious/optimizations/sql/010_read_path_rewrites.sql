-- =============================================================================
-- 010_read_path_rewrites.sql — measured rewrites for the sonyliv_prod client
--
-- Every "before" and "after" number here was measured on the live service
-- (sonyliv, aws ap-south-1, ClickHouse 26.2.1.525, 2 replicas) on 2026-08-02.
-- Nothing is estimated.
--
-- SCOPE. These queries are issued by clients that are NOT in this repository:
-- the sonyliv_prod serving builder and dashboard tier have no source here. This
-- file is therefore the handover artifact — the rewrite, the measurement that
-- justifies it, and the invariant that proves it is equivalent. Apply the
-- rewrite in whichever service owns the query.
--
-- The rewrites are ordered by total time reclaimed, taken from a query_log
-- census over 2026-08-01 22:23:46 -> 2026-08-02 00:17:22. That window covers
-- roughly a quarter of the 7.5-hour run, so execution COUNTS below are a lower
-- bound. Per-query costs and ratios generalise; absolute totals do not.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- R1. max(event_ts) must not be read through events_dedup
--
-- Rank: #1 SELECT by both total time and total bytes read.
-- Observed: 694 executions, 3,127,152,194 rows and 56.3 GB read, 342,847 ms total.
--
-- MEASURED 2026-08-02, same service, back to back, identical answer
-- (2026-08-02 00:13:37.672) from both forms:
--
--   FROM events_dedup   elapsed 1.058 s   bytes_read 162,146,488
--   FROM events_clean   elapsed 0.104 s   bytes_read  72,000,384
--                       -------------------------------------------
--                       10.2x faster, 2.25x fewer bytes
--
-- WHY IT IS SAFE, and this is the whole argument: events_dedup groups by
-- (session_key, event_ts, event_type, event). event_ts is itself a GROUP BY
-- key, so every distinct event_ts in the base table survives into exactly one
-- output group. Grouping can therefore neither add nor remove a value from the
-- domain of event_ts, and max() over the two domains is identical by
-- construction. This reasoning holds ONLY for expressions over GROUP BY keys —
-- it does NOT extend to the 16 argMax columns.
--
-- CLAUDE.md already records events_dedup at 7x on a different query shape. This
-- is the same defect on the hottest path in the workload.

-- BEFORE (do not use):
--   SELECT max(event_ts) FROM sonyliv_prod.events_dedup;

-- AFTER:
SELECT max(event_ts) AS max_event_ts
FROM sonyliv_prod.events_clean;

-- Equivalence check. Run once when adopting the rewrite; it must return 0.
-- Reference-free: it compares the two forms against each other, not against a
-- number someone remembered.
SELECT
    (SELECT max(event_ts) FROM sonyliv_prod.events_dedup) AS via_view,
    (SELECT max(event_ts) FROM sonyliv_prod.events_clean) AS via_base,
    throwIf(via_view != via_base,
            'R1 REWRITE INVALID: events_dedup and events_clean disagree on max(event_ts). '
            'Do not adopt the rewrite until this is explained.') AS ok;


-- -----------------------------------------------------------------------------
-- R2. Never paginate a view whose body has a GROUP BY
--
-- Observed: SELECT * FROM sonyliv_prod.events_dedup LIMIT 31 OFFSET 30 — issued
-- by the ClickHouse SQL console's table browser — took 9,078 ms, read 6,313,780
-- rows / 1.31 GB, and peaked at 6,635,490,818 bytes of RAM to display 31 rows.
-- Highest peak memory of any query in the window.
--
-- LIMIT cannot be pushed below a GROUP BY: the engine must materialise the full
-- 16-argMax aggregation over all of events_clean before it can discard all but
-- 31 rows. There is no rewrite that makes this view cheap to browse.

-- AFTER — browse the base table, which is sorted and supports real pagination:
SELECT *
FROM sonyliv_prod.events_clean
ORDER BY session_key, event_ts
LIMIT 31 OFFSET 30;

-- If genuinely deduplicated rows are needed for a small key set, bound the scan
-- FIRST and deduplicate only what survives:
SELECT
    session_key,
    event_ts,
    event_type,
    event,
    argMax(video_session_id, row_version) AS video_session_id,
    argMax(content_id,       row_version) AS content_id,
    argMax(platform,         row_version) AS platform
FROM sonyliv_prod.events_clean
WHERE session_key IN ({session_keys:Array(UInt64)})
  AND event_ts >= {from_ts:DateTime64(3, 'UTC')}
  AND event_ts <  {to_ts:DateTime64(3, 'UTC')}
GROUP BY session_key, event_ts, event_type, event;


-- -----------------------------------------------------------------------------
-- R3. dirty_sessions: the filter column is not a usable sort-key prefix
--
-- Rank: #2 SELECT by total bytes read.
-- Observed: 649 executions, 433,423,260 rows / 5.85 GB read.
--
-- dirty_sessions is ORDER BY (session_start_date, session_key, last_ingested_at,
-- ingest_batch_id) with NO partition key, and the hot query constrains only
-- last_ingested_at — the THIRD column, with nothing pinning the first two. That
-- is not a prefix, so the primary index cannot prune and the engine scans.
--
-- MEASURED 2026-08-02: 761,874 rows / 12,189,984 bytes read to return 50,000
-- keys — 15:1 read amplification, repeated 649 times in a 1h54m window.
--
-- The table is a plain SharedMergeTree (5,739,016 rows), so unlike the
-- Replacing/Summing tables in this schema it accepts a projection directly.
-- See 020_projections.sql for the fix; the query text itself does not change.

SELECT DISTINCT session_key
FROM sonyliv_prod.dirty_sessions
WHERE last_ingested_at > {since:DateTime64(3, 'UTC')}
LIMIT 50000;


-- -----------------------------------------------------------------------------
-- R4. Do not inline session keys as literals — bind them
--
-- Observed: six normalized_query_hashes produce query text of exactly
-- 99,983-99,985 characters. That is log_queries_cut_to_length (server default
-- 100,000) clipping them, so these statements are UNOBSERVABLE in query_log —
-- the tail is gone and they cannot be diagnosed after the fact.
--
-- The text is dominated by a literal array of session keys inlined TWICE in the
-- same statement: once in empty(_CAST([...], 'Array(UInt64)')) and again in
-- session_key IN _CAST([...], 'Array(UInt64)').
--
-- Two costs, both avoidable: the statement is re-parsed and re-planned on every
-- call because no two calls share query text, and it is untraceable in the log.

-- AFTER — one bound parameter, referenced twice, constant query text:
SELECT session_key, event_ts, event_type, event
FROM sonyliv_prod.events_clean
WHERE event_ts <= {evaluation_as_of:DateTime64(3, 'UTC')}
  AND (empty({session_keys:Array(UInt64)})
       OR session_key IN {session_keys:Array(UInt64)});


-- -----------------------------------------------------------------------------
-- R5. FINAL hidden inside a view body
--
-- Observed: FINAL appears in 688 of 5,183 sonyliv_prod SELECTs. The problem is
-- not the count, it is that serving_live_content and serving_live_total both
-- embed FINAL in the view body, so a caller reading the view cannot see that it
-- is paying for it.
--
-- This matters more than the CPU: per the official docs, a SELECT with FINAL
-- cannot use a projection at all. Every FINAL baked into a view permanently
-- forecloses the projection route for every query that reads it.
--
-- Two supported ways out, in order of preference:
--
--   (a) If the ReplacingMergeTree key is genuinely unique per logical row and
--       the query aggregates, drop FINAL and deduplicate in the aggregate —
--       argMax over the version column gives the same answer without FINAL.
--
--   (b) If FINAL is genuinely required, keep it but make it VISIBLE: name the
--       view *_final so callers know, and do not add a projection to that table
--       expecting it to be used.
--
-- Pattern (a), the version-column form:
SELECT
    bucket_start,
    dim_mask,
    content_id,
    argMax(bucket_peak,         version) AS bucket_peak,
    argMax(ending_concurrency,  version) AS ending_concurrency,
    argMax(active_ms,           version) AS active_ms
FROM sonyliv_prod.serving_concurrency_live
WHERE bucket_start >= {from_ts:DateTime64(3, 'UTC')}
GROUP BY bucket_start, dim_mask, content_id;

-- Equivalence check for R5(a). Must return 0 differing rows before adoption.
SELECT count() AS differing_rows,
       throwIf(differing_rows > 0,
               'R5 REWRITE INVALID: the argMax form disagrees with FINAL. '
               'The sort key is probably not unique per logical row.') AS ok
FROM (
    SELECT bucket_start, dim_mask, content_id, bucket_peak, ending_concurrency, active_ms
    FROM sonyliv_prod.serving_concurrency_live FINAL
    EXCEPT
    SELECT bucket_start, dim_mask, content_id,
           argMax(bucket_peak, version),
           argMax(ending_concurrency, version),
           argMax(active_ms, version)
    FROM sonyliv_prod.serving_concurrency_live
    GROUP BY bucket_start, dim_mask, content_id
);


-- -----------------------------------------------------------------------------
-- R6. Stop rebuilding serving_concurrency_live in full every cycle
--
-- Observed: 314 executions writing an average of 41,160 rows each (min 35,761,
-- max 46,233 — a tight band, so each run rewrites essentially the same set),
-- 12,924,211 rows written in total, into a table that holds 149,097 rows.
-- 87x write amplification, into a SharedReplacingMergeTree where every rewritten
-- row becomes merge work that must later be collapsed away again.
--
-- The fix is not a query rewrite, it is a bounded one: rebuild only the buckets
-- that can still change. Everything older than the liveness timeout (120 s) is
-- sealed and cannot move, so re-emitting it is pure waste.
--
-- Add the bound to the builder's WHERE, and it stops being a full rebuild:
--
--     WHERE bucket_start >= (SELECT watermark_ts FROM sonyliv_prod.serving_watermark FINAL
--                            WHERE layer = 'live') - INTERVAL 120 SECOND
--
-- Conservation check that the bounded rebuild did not lose sealed history —
-- reference-free, compares the layer against its own input:
SELECT
    (SELECT count() FROM sonyliv_prod.serving_concurrency_live
      WHERE bucket_start < {sealed_before:DateTime64(3, 'UTC')}) AS sealed_rows_after,
    {sealed_rows_before:UInt64}                                  AS sealed_rows_before,
    throwIf(sealed_rows_after < sealed_rows_before,
            'R6 REGRESSION: the bounded rebuild dropped sealed buckets. '
            'The lower bound is too high.') AS ok;


-- -----------------------------------------------------------------------------
-- R7. Control-plane tables written one row per statement
--
-- Observed: serving_watermark 686 INSERTs x 1 row (32,688 ms),
-- serving_watermark_history 686 INSERTs x 1 row (31,690 ms),
-- concurrency_watermark 26 INSERTs x 1 row (1,116 ms).
-- 1,398 statements, 1,398 rows, 65,494 ms. Each creates a part.
--
-- Separately, sonyliv_prod.ingest_batches took 5,463 INSERTs of a median 2 rows
-- each — 67.3 ms of server time per audit row, the #3 pattern by total time in
-- the entire workload, ahead of every SELECT.
--
-- These are genuinely un-batchable client-side: the row exists only when the
-- cycle ends. That is exactly the case async inserts are for — the server
-- buffers across clients and cuts one properly sized part.
--
-- Apply per INSERT (wait_for_async_insert=1 keeps durability confirmed before
-- the call returns; fire-and-forget would hide a failed write):
--
--     SETTINGS async_insert = 1, wait_for_async_insert = 1
--
-- Note for anyone adding a dedup token to these: async_insert_deduplicate
-- defaults to 0 (measured on this service 2026-08-02: value=0 default=0
-- changed=0), so insert_deduplication_token is INERT on the async path unless
-- async_insert_deduplicate = 1 is set alongside it. The same correction is
-- applied in this repo's Go client at ingest/internal/chx/loader.go.
