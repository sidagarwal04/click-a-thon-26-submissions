-- ============================================================================
-- 12_publish.sql — CONTINUOUS PUBLICATION. The state the finalizer runs on.
--
-- README_START_HERE step 4 is "Publish continuously updated aggregates for
-- downstream consumers". Until now the honest answer was "by recomputing":
-- tools/build-model.sh TRUNCATEs session_intervals and cc_minute_delta and
-- rebuilds both from all of ev_raw. This file is the state that lets
-- tools/publish.sh do it INCREMENTALLY instead — see ADR 0013.
--
-- The mechanism in one paragraph. An incremental materialized view on ev_raw
-- writes, per insert block, the set of sessions that block touched, stamped
-- with INGEST time (`session_dirty`). A finalizer claims everything marked
-- since its cursor, re-derives ONLY those sessions from ev_raw, appends the
-- NEGATION of their currently-published deltas and then their new deltas
-- (ADR 0006 correction-by-diff), promotes the new intervals, re-derives the
-- hour-tier rows and user-minute buckets the batch touched (ADR 0016), and
-- advances the cursor. Nothing is truncated and nothing is rebuilt.
--
-- WHY THIS IS EXACT, and not an approximation. A session's contribution to
-- cc_minute_delta is a pure function of THAT SESSION'S intervals alone:
-- sql/40_deltas.sql groups by video_session_id, merges that session's runs,
-- hour-clips them, and only then sums into the (minute, dims) grain. No
-- cross-session term exists. So for a touched set S,
--
--     published(S)  :=  deltas(intervals_old(S))
--     wanted(S)     :=  deltas(intervals_new(S))
--
-- and appending `wanted(S) - published(S)` into an AggregatingMergeTree of
-- SimpleAggregateFunction(sum, Int64) converges on exactly the value a full
-- rebuild would have written. Sessions outside S are untouched and their terms
-- are unchanged. This is a rebuild — of one session at a time.
--
-- WHY THE WATERMARK IS NO LONGER A GATE. ADR 0004 split serving into a sealed
-- tier behind a watermark W and a hot tier in front of it, because a straggler
-- older than W had no path. Correction-by-diff IS that path, and it does not
-- care how old the straggler is: a late event marks its session dirty, the next
-- batch re-derives that session in full and diffs. W survives only as a
-- FRESHNESS LABEL (v_cc_publish_lag below), not as a control knob. See ADR 0013.
--
-- SAFE ON A FRESH DATABASE, AND NO REBUILD TO CATCH UP. Every object here is
-- CREATE ... IF NOT EXISTS and holds no data. On a fresh database the first
-- bulk load fires mv_session_dirty, every session is marked, and the first
-- publish run derives all of them — the initial build and every later update
-- run down the SAME code path, so there is no bootstrap special case to get
-- wrong. On an ALREADY-BUILT database nothing is marked, the cursor starts at
-- the current ingest position, and the first run has nothing to do: applying
-- this file to a populated service costs one DDL round trip and does NOT
-- trigger a re-derivation of history.
--
-- MIGRATING A PRE-ADR-0019 INSTALL. ADR 0019 changed two identities:
-- session_dirty and cc_publish_consumed now carry `insert_id`
-- (initialQueryID() of the INSERT that fired the MV), and the consumed set is
-- keyed (marked_at, insert_id) — a timestamp alone cannot tell two
-- same-millisecond inserts apart (measured suppression: Q10). CREATE IF NOT
-- EXISTS cannot change an existing key, so on a database that already has the
-- old objects run, with NO publisher running and no in-flight run:
--     DROP TABLE mv_session_dirty; DROP TABLE cc_publish_consumed;
-- then re-apply this file. Dropping cc_publish_consumed forgets which inserts
-- were digested; markings still inside session_dirty's 7-day TTL are then
-- re-claimed once and republished — a no-op by idempotence (proven in
-- evidence/publish.txt PHASE 8), not a correctness event. tools/publish.sh
-- refuses to run against a half-migrated schema and prints these commands.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- session_dirty — the change log. One row per (session, insert block).
--
-- This is the piece that makes the pipeline event-driven rather than
-- scheduled-scan. ADR 0006 suggested the finalizer find stragglers by
-- "comparing the max event timestamp it has processed per session against what
-- it processed previously", which is a GROUP BY over all of ev_raw on every
-- run — O(history) work per batch, i.e. exactly the "only works at hackathon
-- size" shape the problem statement calls out. An incremental MV sees only the
-- current insert block, which is precisely the right amount of information:
-- whatever just arrived is what needs re-deriving.
--
-- `marked_at` is INGEST time (now64(3) at insert), NOT event time. That
-- distinction is the whole point — a straggler carrying an event_timestamp
-- from 40 minutes ago still gets a marked_at of now, so the cursor finds it.
--
-- ORDER BY (marked_at, ...) so the finalizer's `WHERE marked_at > cursor` is a
-- primary-key prefix range and costs granules, not a scan.
--
-- min/max_event_ts are carried so the finalizer can bound its read of ev_raw
-- by event time as well as by session id — see tools/publish.sh, and note the
-- completeness argument there: it is not a heuristic.
--
-- TTL 7 days: this is a queue, not history. The runs log below is the audit
-- trail. Nothing reads session_dirty behind the committed cursor.
-- ---------------------------------------------------------------------------
-- `insert_id` (ADR 0019) is initialQueryID() — the server-assigned UUID of the
-- INSERT that fired the MV. It is what marked_at was pretending to be: an
-- identity for the insert. Two inserts landing in the same millisecond carry
-- the same marked_at but can never carry the same insert_id, and the consumed
-- set below keys on the PAIR. Verified on Cloud 26.2.1.525: initialQueryID()
-- is constant-folded per query (legal alongside GROUP BY, one value across
-- groups) and distinct across inserts.
CREATE TABLE IF NOT EXISTS session_dirty
(
    marked_at        DateTime64(3),
    insert_id        String,
    video_session_id String,
    min_event_ts     DateTime64(3),
    max_event_ts     DateTime64(3),
    events           UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(marked_at)
ORDER BY (marked_at, video_session_id)
TTL toDateTime(marked_at) + INTERVAL 7 DAY
SETTINGS min_bytes_for_wide_part = 0;

-- Heals a pre-ADR-0019 session_dirty on re-apply (CREATE IF NOT EXISTS cannot
-- add a column). Old rows read back insert_id = '' — they are all re-claimed
-- exactly once after the consumed table is dropped per the migration note.
ALTER TABLE session_dirty ADD COLUMN IF NOT EXISTS insert_id String AFTER marked_at;

-- Fires on every insert into ev_raw — the bulk load, the unseen day, a single
-- replayed straggler. GROUP BY collapses the block to one row per session, so
-- a 905,558-row load writes ~10,866 rows here, not 905,558.
--
-- now64(3) is constant-folded per query, so it is legal alongside GROUP BY and
-- every session in one block shares one marked_at. Verified on Cloud 26.2.1.525
-- before this file was written; two loads a second apart produce two distinct
-- marked_at values, which is what the cursor needs.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_session_dirty TO session_dirty AS
SELECT
    now64(3)             AS marked_at,
    initialQueryID()     AS insert_id,
    video_session_id,
    min(event_timestamp) AS min_event_ts,
    max(event_timestamp) AS max_event_ts,
    toUInt32(count())    AS events
FROM ev_raw
GROUP BY video_session_id;


-- ---------------------------------------------------------------------------
-- cc_publish_batch — the sessions one run has claimed, frozen.
--
-- Frozen deliberately. The run's four heavy statements must all see the SAME
-- session set; reading `session_dirty WHERE marked_at > cursor` four times
-- would let an insert landing mid-run into some statements and not others, and
-- the negation would then not match the emission. Claim once, then join.
--
-- lo_event_ts/hi_event_ts are the per-session read window (see publish.sh).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cc_publish_batch
(
    run_id           UInt64,
    video_session_id String,
    lo_event_ts      DateTime64(3),
    hi_event_ts      DateTime64(3)
)
ENGINE = MergeTree
PARTITION BY run_id
ORDER BY (run_id, video_session_id)
TTL toDateTime(fromUnixTimestamp(intDiv(run_id, 1000))) + INTERVAL 7 DAY
SETTINGS min_bytes_for_wide_part = 0;


-- ---------------------------------------------------------------------------
-- cc_publish_consumed — which INSERTs the finalizer has already digested.
--
-- A scalar timestamp cursor alone is not enough, and the first run of
-- tools/publish-test.sh proved it: with a cursor plus a safety lookback, every
-- run re-claimed the whole of the previous run's batch, because the previous
-- batch's marked_at sits exactly ON the cursor. 6,659 sessions were re-derived
-- to absorb 5. Harmless — re-publishing an unchanged session appends
-- -deltas(X) + deltas(X) = 0 — but it turns an incremental update back into a
-- rebuild, which is the entire thing this design exists to avoid.
--
-- now64(3) is constant-folded per QUERY, so every row an INSERT produces here
-- carries ONE marked_at: one row per insert, not per session and not per
-- event. (Measured: a 458,477-row load landing in 7 parts produced exactly 1
-- distinct marked_at.) That makes exact set-bookkeeping cheap, and it removes
-- the redundant work entirely rather than bounding it.
--
-- BUT marked_at alone is NOT an identity (ADR 0019, Q10). Two inserts in the
-- same millisecond share a marked_at, and if the slower one's rows become
-- visible after the faster one was consumed, a timestamp-keyed set suppresses
-- the slower insert FOR EVER (reproduced before this key was changed). The key
-- is therefore the PAIR (marked_at, insert_id): the settle rule makes the race
-- improbable; the pair makes it impossible to mistake one insert for another.
-- marked_at stays first in the key so the finalizer's cursor-range read is
-- still a primary-key prefix.
--
-- Pairs with the SETTLE rule in tools/publish.sh: a marking is only eligible
-- once it is PUBLISH_SETTLE_S old, so an insert still committing cannot be
-- half-consumed and then marked done. If an insert outlives even the settle
-- window, the claim's LOOKBACK re-scans a bounded stretch behind the cursor
-- and the pair-keyed set makes that re-scan exact instead of a re-derivation.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cc_publish_consumed
(
    marked_at DateTime64(3),
    insert_id String,
    run_id    UInt64
)
ENGINE = ReplacingMergeTree
ORDER BY (marked_at, insert_id)
TTL toDateTime(marked_at) + INTERVAL 7 DAY
SETTINGS min_bytes_for_wide_part = 0;


-- ---------------------------------------------------------------------------
-- cc_publish_lease — at most one live publisher per database (ADR 0019, Q9).
--
-- ClickHouse has no server-side compare-and-set, so mutual exclusion is built
-- from the one primitive it does have — atomic visible-or-not INSERT — plus a
-- deterministic tiebreak that every observer computes identically:
--
--   1. DECLINE GATE.  A candidate first reads the live set (released = 0,
--      renewed_at within PUBLISH_LEASE_TTL_S). If any live lease exists, it
--      declines without inserting. This keeps steady state quiet.
--   2. LOTTERY.  Otherwise it inserts its own lease row (owner = a fresh UUID,
--      acquired_at = server now64(3)), waits PUBLISH_LEASE_SETTLE_S — the same
--      insert-visibility assumption the marking queue already makes — and then
--      selects the winner among live leases: greatest (acquired_at, owner).
--      Everyone who looks computes the same winner; losers exit.
--   3. FENCING.  The holder re-inserts (renewed_at = now) and re-checks the
--      winner before EVERY write phase. NEWEST acquisition wins deliberately:
--      a new acquirer can only exist after the old lease expired, so
--      newest-wins means a revived zombie loses to its replacement rather
--      than stealing the run back mid-flight.
--
-- ReplacingMergeTree(renewed_at) keyed by owner keeps one row per publisher;
-- release is an explicit tombstone (released = 1 at a newer renewed_at), so a
-- clean exit hands over immediately instead of waiting out the TTL.
--
-- What this does NOT guarantee (recorded honestly in ADR 0019): a statement
-- already in flight server-side when its issuer loses the lease cannot be
-- fenced — the run-scoped insert_deduplication_token and the idempotent
-- DELETE are the last line of defence there, and the two-publisher test in
-- tools/publish-test.sh exercises exactly that seam.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cc_publish_lease
(
    owner       String,
    acquired_at DateTime64(3),
    renewed_at  DateTime64(3),
    released    UInt8,
    host        String,
    pid         UInt32
)
ENGINE = ReplacingMergeTree(renewed_at)
ORDER BY owner
TTL toDateTime(renewed_at) + INTERVAL 1 DAY
SETTINGS min_bytes_for_wide_part = 0;


-- ---------------------------------------------------------------------------
-- cc_publish_runs — the write-ahead log, the cursor, and the audit trail.
--
-- One row per PHASE per run, appended as that phase completes. Three jobs:
--
--   1. THE CURSOR.  max(cursor_to) over committed runs. Nothing else stores it.
--   2. CRASH RECOVERY.  A run's four heavy statements are not one transaction.
--      The phase markers say which ones landed, so a resumed run continues
--      instead of restarting — restarting would negate a second time.
--      Belt and braces: each heavy statement also carries
--      insert_deduplication_token = '<run_id>:<phase>', so a replay of a
--      statement that DID land is dropped by the server rather than doubled.
--      Verified on SharedAggregatingMergeTree before this file was written.
--   3. OBSERVABILITY.  Batch size, row counts and per-phase wall clock, which
--      is what v_cc_publish_lag and ClickStack read.
--
-- Phases, in order:
--   claiming  INTENT (ADR 0019). Written BEFORE the batch and consumed inserts,
--             so no side effect of the claim can exist without a run row that
--             names it. A run that dies here is ROLLED BACK on the next start:
--             its consumed rows deleted, its batch partition dropped, and the
--             run marked aborted — the markings become claimable again.
--             Before this phase existed, a crash between the consumed insert
--             and the claimed mark orphaned the batch for ever (Q8, reproduced).
--   claimed   the batch table is written, the read window is known, and the
--             note carries this run's build_version (bv=N) — resume MUST reuse
--             it: recomputing BV on resume made the prune delete the crashed
--             run's own derivation (Q8b, reproduced).
--   negated   -deltas(intervals_old(batch)) appended to cc_minute_delta
--   derived   intervals_new(batch) inserted into session_intervals @ build_version
--   pruned    intervals_old(batch) removed (build_version < this run's)
--   emitted   +deltas(intervals_new(batch)) appended to cc_minute_delta
--   hours     cc_hour_agg re-derived for the batch's touched hours (ADR 0016)
--   users     cc_user_minute re-derived for the batch's touched minutes (ADR 0016)
--   committed cursor advanced; the run is durable
--   aborted   terminal, like committed, but the cursor did NOT move: an empty
--             claim, or a rolled-back claiming-phase crash
--
-- WHY `pruned` EXISTS. session_intervals is ReplacingMergeTree keyed
-- (video_session_id, interval_start), which replaces a key but cannot delete
-- one. A re-derivation can legitimately make an interval VANISH — a straggler
-- landing inside a gap merges two runs into one, so the second run's start key
-- no longer exists. Without the prune, FINAL keeps that orphan for ever, the
-- interval-expansion views over-count, and — worse — the NEXT run's negation
-- would negate deltas that were never published, so the error would compound
-- rather than sit still. This is the same class of bug as the
-- ReplacingMergeTree(interval_end) defect in sql/10_intervals.sql: a merge rule
-- that assumes re-derivation can only ever add.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cc_publish_runs
(
    run_id       UInt64,
    phase        LowCardinality(String),
    at           DateTime64(3),
    cursor_from  DateTime64(3),
    cursor_to    DateTime64(3),
    sessions     UInt32,
    rows_written UInt64,
    elapsed_ms   UInt32,
    note         String
)
ENGINE = MergeTree
ORDER BY (run_id, at)
SETTINGS min_bytes_for_wide_part = 0;


-- ---------------------------------------------------------------------------
-- v_cc_publish_lag — REFRESH LATENCY, which is the third column of the
-- statement's core-aggregation table and the one v_cc_watermark could not
-- answer.
--
-- v_cc_watermark (sql/85_windows.sql) reports EVENT-time staleness: how far the
-- newest sealed minute is from the newest event. That is the right metric for a
-- batch-rebuilt model, and it has a documented sign trap — a caught-up model
-- reads NEGATIVE because TAIL_S pushes the sealed minute past the last event.
--
-- This view reports INGEST-time staleness instead: how long ago the newest
-- arrival that the serving layer has actually absorbed came in. It is the
-- number an operator wants ("are the aggregates current?") and it cannot go
-- negative. The two are complements, not rivals — keep both.
--
-- pending_sessions is the queue depth: sessions marked dirty that the serving
-- layer has not yet re-derived. Zero means the aggregates are exact as of
-- publish_cursor. It is the alerting signal, because publish_lag_s alone looks
-- healthy on an idle stream where nothing has arrived to be late.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cc_publish_lag AS
WITH
    (SELECT max(cursor_to) FROM cc_publish_runs WHERE phase = 'committed') AS cursor_,
    (SELECT max(marked_at)  FROM session_dirty)                            AS ingest_wm,
    (SELECT max(run_id)     FROM cc_publish_runs WHERE phase = 'committed') AS last_run,
    -- Oldest marking the finalizer has NOT digested. This is the row the
    -- 7-day TTL will eat first: its age against that TTL is the retention
    -- headroom (Q11) — session_dirty is a QUEUE, and a TTL on a queue is a
    -- deadline, not housekeeping. Keyed on the (marked_at, insert_id) PAIR,
    -- same identity as the claim predicate (ADR 0019). minOrNull, not min:
    -- a plain min over the empty set returns the epoch, and an empty queue
    -- must read as NULL headroom, not as a 56-year breach.
    (SELECT minOrNull(marked_at) FROM session_dirty
      WHERE (marked_at, insert_id) NOT IN
            (SELECT marked_at, insert_id FROM cc_publish_consumed))        AS oldest_pending
SELECT
    cursor_    AS publish_cursor,      -- ingest position the serving layer is exact as of
    ingest_wm  AS ingest_watermark,    -- newest arrival the change log has seen

    -- POSITIVE = the finalizer is behind by this many seconds of ARRIVALS.
    -- Never negative, unlike v_cc_watermark.sealed_lag_s.
    greatest(0, dateDiff('second', cursor_, ingest_wm))       AS publish_lag_s,

    -- Queue depth. The signal that matters: a lag of 0 on an idle stream is
    -- not the same as a lag of 0 on a busy one. Counted against the digested
    -- SET, not against the cursor — an insert whose marking ties the cursor is
    -- pending or not depending on whether it was consumed, and only
    -- cc_publish_consumed knows which. The identity is the pair — a
    -- marked_at-only test also inherited Q10's blindness and reported 0
    -- pending while a suppressed insert sat unserved (reproduced).
    (SELECT uniqExact(video_session_id) FROM session_dirty
      WHERE (marked_at, insert_id) NOT IN
            (SELECT marked_at, insert_id FROM cc_publish_consumed))
                                                              AS pending_sessions,

    -- RETENTION HEADROOM (Q11, ADR 0019). session_dirty / cc_publish_batch /
    -- cc_publish_consumed all carry QUEUE_TTL_DAYS TTLs; work that outlives
    -- them expires SILENTLY and the tiers are wrong with no signal. These
    -- columns are that signal: headroom is seconds until the oldest undigested
    -- marking hits the TTL, and the alert trips a full day before the cliff.
    -- Wire retention_alert (and pending_sessions alongside it) into `sonyliv
    -- observe` / ClickStack; alert when retention_alert = 1 OR when
    -- publish_lag_s grows monotonically across scrapes.
    --
    -- The seconds were a hardcoded 604800 in three places here. A VIEW can read
    -- the policy, so it does (ADR 0032). The table TTLs above cannot — a
    -- ClickHouse TTL must be a deterministic expression over the table's own
    -- columns — so they keep the literal and `tools/policy.sh check` asserts
    -- they equal QUEUE_TTL_DAYS. Declared-and-verified where injection is
    -- impossible; injected everywhere it is possible.
    (SELECT toInt64(queue_ttl_days) * 86400 FROM v_model_policy)
                                                              AS retention_ttl_s,
    if(oldest_pending IS NULL, NULL,
       greatest(0, dateDiff('second', oldest_pending, now())))
                                                              AS oldest_pending_age_s,
    if(oldest_pending IS NULL, NULL,
       retention_ttl_s - dateDiff('second', oldest_pending, now()))
                                                              AS retention_headroom_s,
    if(oldest_pending IS NULL, 0,
       toUInt8(dateDiff('second', oldest_pending, now()) > retention_ttl_s - 86400))
                                                              AS retention_alert,

    -- The live publisher lease, if any (ADR 0019). Winner rule matches
    -- tools/publish.sh: newest (acquired_at, owner) among live rows. The
    -- liveness window is PUBLISH_LEASE_TTL_S, read from the same declaration
    -- the publisher reads (ADR 0032) — it was a third copy of the value, in a
    -- third file, that no test bound to the other two (DYNAMIC_PARAMS C5).
    -- Informational only; the publisher evaluates its own TTL, this column
    -- just shows the holder.
    (SELECT owner FROM (
        SELECT owner, min(acquired_at) AS acq, max(renewed_at) AS ra,
               argMax(released, renewed_at) AS rel
        FROM cc_publish_lease GROUP BY owner)
      WHERE rel = 0 AND ra > now64(3) - toIntervalSecond((SELECT publish_lease_ttl_s FROM v_model_policy))
      ORDER BY acq DESC, owner DESC LIMIT 1)                  AS lease_holder,

    last_run                                                  AS last_committed_run,
    (SELECT sum(elapsed_ms) FROM cc_publish_runs
      WHERE run_id = last_run)                                AS last_run_ms,
    (SELECT sessions FROM cc_publish_runs
      WHERE run_id = last_run AND phase = 'committed')        AS last_run_sessions,

    -- Has a run started and not finished? Non-zero means a crashed or in-flight
    -- run; tools/publish.sh resumes it rather than starting a new one.
    -- 'aborted' is terminal (empty claim or rolled-back claiming crash).
    (SELECT count() FROM (
        SELECT run_id FROM cc_publish_runs
        GROUP BY run_id
        HAVING countIf(phase IN ('committed', 'aborted')) = 0))            AS runs_in_flight
FROM system.one;
