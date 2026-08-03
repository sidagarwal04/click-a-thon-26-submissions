-- sql/60_projection.sql — session-ordered PROJECTION on ev_raw
--
-- Summary: adds `proj_by_session`, a normal PROJECTION over ev_raw ordered by
-- (video_session_id, event_timestamp). Recovers point-lookup-by-session performance for
-- the finalizer and straggler/late-arrival paths WITHOUT touching the base table's sort
-- key. NAMES NO DATABASE (ADR 0010): apply with `tools/apply-sql.sh --database <db>`.
-- Run after sql/00_schema.sql and after ev_raw is loaded. Idempotent.
--
-- WHY (see docs/adr/0002-order-by-time-bucket-then-platform.md and docs/adr/0021):
--   ADR 0002 moved ev_raw's ORDER BY from (video_session_id, event_timestamp) to
--   (toStartOfHour(event_timestamp), platform, video_session_id, event_timestamp) — measured
--   17.3x better on the dashboard shape, because a 64-char near-unique hash in the key prefix
--   lets the sparse index skip nothing (rule `schema-pk-cardinality-order`, impact CRITICAL).
--   That decision stands and is NOT reverted here.
--
--   ADR 0002's own Consequences section names the remedy for the access pattern it gave up:
--     "If a 'single session lookup' access pattern ever becomes hot, add a PROJECTION ordered
--      by video_session_id rather than reverting the key."
--   That pattern IS hot for us: the interval finalizer and the late-arrival/straggler path both
--   fetch every event of a *named* set of sessions. Under ADR 0002's key those queries can only
--   prune the granules where (hour, platform) happens to stay constant across a granule run —
--   measured 104,640 of 905,559 rows (11.6%) for the finalizer's windowed one-session derive.
--   With the projection the same query reads 8,193 rows (0.9%) — 12.8x — see ADR 0021.
--
--   A projection is a second, independently-sorted copy of the data stored inside each part.
--   The query planner picks it automatically (optimize_use_projections=1); no query is rewritten.
--   Partition pruning still applies, and the base table's dashboard performance is untouched.
--
-- COST: the projection is a full second copy of every column, sorted by a high-entropy hash,
--   so it compresses far worse than the base table: measured +91% on ev_raw
--   (3.73 -> 7.16 MiB). ADR 0021 records the decision and both sides of the trade.
--
-- THIS FILE NAMES NO DATABASE. The database comes from how the file is applied
-- (`clickhouse-client --database "$DB"` / HTTP ?database= — see tools/apply-sql.sh),
-- never from the text. An earlier version hard-coded `sonyliv.`, which made the file
-- unusable against a scratch database — the same defect ADR 0010 fixed in sql/80_content.sql,
-- and the reason evidence/publish.txt PHASE 10 had to issue this ALTER by hand.

ALTER TABLE ev_raw
    ADD PROJECTION IF NOT EXISTS proj_by_session
    (
        SELECT *
        ORDER BY (video_session_id, event_timestamp)
    );

-- Rewrites every active part to build the projection. On 905K rows this is seconds, but it IS
-- a mutation: confirm it drained before trusting any "after" measurement.
--   SELECT * FROM system.mutations
--   WHERE database = currentDatabase() AND table = 'ev_raw' AND NOT is_done;
ALTER TABLE ev_raw MATERIALIZE PROJECTION proj_by_session;
