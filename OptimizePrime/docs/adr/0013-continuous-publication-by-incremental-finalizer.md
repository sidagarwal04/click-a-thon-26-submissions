# ADR 0013 — Continuous publication by one incremental finalizer, and the retirement of the two-tier split

> **Summary:** README step 4 — "publish continuously updated aggregates" — is now true rather than
> aspirational. An incremental MV on `ev_raw` records which sessions each INSERT touched
> (`session_dirty`); `tools/publish.sh` claims what has arrived since its cursor, re-derives ONLY
> those sessions, and appends the negation of their published deltas plus their new ones
> ([ADR 0006](0006-late-arrival-correction-by-diff.md)). Nothing is truncated, nothing is rebuilt.
> The load-bearing claim: correction-by-diff makes the **hot tier unnecessary and the watermark not a
> gate**, so [ADR 0004](0004-two-tier-lambda-serving.md)'s two tiers collapse to one and
> [ADR 0005](0005-heartbeat-lease-semantics.md) stays unbuilt for a *reason* rather than pending a
> decision. Measured: incremental output is byte-identical to a full rebuild across 1,579 minutes at
> every stage; a one-session straggler correction costs 3.4 s and reads 11.6% of `ev_raw`.
> Status: accepted, 2026-08-01. Proven in `evidence/publish.txt`, never applied to `sonyliv`.

**Status** Accepted · 2026-08-01 · supersedes the serving-topology half of
[ADR 0004](0004-two-tier-lambda-serving.md); resolves [ADR 0005](0005-heartbeat-lease-semantics.md)
by declining to build it; makes [ADR 0006](0006-late-arrival-correction-by-diff.md) live ·
**amended by [ADR 0016](0016-publisher-owns-the-user-and-hour-tiers.md)** — as accepted, this
finalizer maintained only `session_intervals` and `cc_minute_delta`; the user and hour/day tiers
went stale (Codex audit §4.1). ADR 0016 adds the `hours` and `users` phases that close that gap.

## Context

`tools/build-model.sh` TRUNCATEs `session_intervals` and `cc_minute_delta` and re-derives both from
all of `ev_raw`. The problem statement scores "update handling: incrementally, or by recomputing?"
and warns against "choices that only work at hackathon size". Our honest answer was *by recomputing*,
and `WALKTHROUGH.md` §5 named it the biggest remaining gap.

Three designs were already on the table and none was live:

- **[ADR 0004](0004-two-tier-lambda-serving.md)** — a hot tier of heartbeat leases stitched at a
  watermark `W = 2400 s` to an append-only sealed tier. Sealed tier built; **finalizer never built**.
- **[ADR 0005](0005-heartbeat-lease-semantics.md)** — the hot tier's lease semantics. **Blocked**:
  leases renew straight through a `pause` (0.756 beats/min, inside `LEASE = 150 s`), so the hot tier
  is provably equivalent to the gap-only model that [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md)
  discarded. Upper bound on the inflation: 834 h of paused time against a 1,949 h answer.
- **[ADR 0006](0006-late-arrival-correction-by-diff.md)** — correction-by-diff, arithmetic proven
  exact but only inside `sql/70_truncation_test.sql`. **No live path.**

## Decision

Build **one** thing: an incremental finalizer that applies correction-by-diff to every session that
has received events since its cursor. Do not build the hot tier.

**1 · The change log is a materialized view, not a scan.** `mv_session_dirty` fires on every INSERT
into `ev_raw` and writes one row per session per insert into `session_dirty`, stamped with **ingest**
time. ADR 0006 proposed finding stragglers by comparing per-session max event timestamps against the
previous run — a `GROUP BY` over all history on every batch, which is precisely the shape the
statement calls out. An incremental MV sees only the current insert block, which is exactly the
information needed: whatever just arrived is what needs re-deriving. Measured: a 458,477-row load
produced 6,659 change-log rows in one block.

**2 · The finalizer is four statements over a claimed batch**, each recorded in `cc_publish_runs`
as it lands: `negate` (append `−deltas(intervals_old)`), `derive` (re-derive from `ev_raw` at a new
`build_version`), `prune`, `emit` (append `+deltas(intervals_new)`), then commit the cursor.

**3 · The derivation SQL is not reimplemented.** `tools/publish.sh` sed-templates
`sql/30_build_intervals.sql` and `sql/40_deltas.sql` — the idiom `tools/truncation-test.sh` already
uses — so the incremental path cannot drift from the batch path. Every substitution is asserted; a
sed anchor that stopped matching would silently turn the scoped read into a full one, which is the
exact claim this ADR makes.

**4 · The watermark is demoted from a gate to a label.** ADR 0004 needed `W` because a sealed minute
had no path back. Correction-by-diff *is* that path and does not care how old the straggler is, so
nothing has to be held back. `v_cc_watermark` keeps reporting event-time staleness; the new
`v_cc_publish_lag` reports **ingest-time** staleness and queue depth, which is the number that
answers "are the aggregates current?".

**5 · The hot tier is declined, not deferred.** See *Why*.

## Why

**The diff is exact because a session's contribution is separable.** `sql/40_deltas.sql` groups by
`video_session_id`, merges that session's runs, hour-clips them, and only then sums into the
`(minute, dims)` grain. There is no cross-session term. So for a touched set `S`, appending
`deltas(intervals_new(S)) − deltas(intervals_old(S))` into an `AggregatingMergeTree` of
`SimpleAggregateFunction(sum, Int64)` lands on exactly what a rebuild would write. It is a rebuild —
of one session at a time.

**The hot tier's whole job disappears.** It existed to answer minutes newer than `W` while the sealed
tier lagged 40 minutes behind. With a finalizer running every minute the sealed tier lags seconds, so
the hot tier would buy sub-minute freshness at the price of counting paused time as watching — an
error of the same order as the answer. Declining it is the smaller *and* the more correct scope.

**And it does not cost the mandated comparison.** The statement requires session-aware vs
session-independent side by side, and `cc_minute_stateless` already is the session-independent model:
**2,894 at the peak minute against the session-aware 2,917**. Note that this is *not* the "upper
bound" relabel ADR 0005 option 3 proposed — `cc_minute_stateless` credits only the minute a beat
lands in, with no lease fan-out, so it reads **lower** than the sealed tier, not higher. Option 3's
wording would have been a false label; the honest move is to decline the lease tier and leave the
existing baseline under its accurate name.

**Bootstrap and steady state are the same code.** On a fresh database the first load marks every
session dirty and the first run derives all of them. There is no separate initial-build path to drift.
On an already-built database nothing is marked, so applying this costs one DDL round trip and does
**not** trigger a re-derivation of history — the "no rebuild to catch up" requirement, satisfied by
construction rather than by a migration script.

**Over-consuming is safe, under-consuming is not.** Re-publishing an unchanged session appends
`−deltas(X) + deltas(X) = 0`. That asymmetry is why the design tolerates replays, resumed runs and
operator-forced corrections. Measured in PHASE 6: 200 unchanged sessions republished, 1,354 rows
appended, **0 of 1,579 minutes moved**.

## What this cost, measured

All from `evidence/publish.txt`, Cloud 26.2.1.525, 905,558 events / 10,866 sessions.

| Stage | Sessions | Wall clock | Delta rows appended | Convergence vs rebuild |
|---|---|---|---|---|
| initial build (via the finalizer) | 6,659 | 5.5 s | 14,879 | 0 differing of 1,544 minutes |
| 5 open sessions catch up | 5 | 4.6 s | 47 | 0 differing of 1,554 minutes |
| the whole remaining stream | 7,718 | 3.9 s | 27,550 | 0 differing of 1,579 minutes |
| **one straggler, 46 min behind** | **1** | **3.4 s** | **10** | **0 differing of 1,579 minutes** |
| 200 unchanged, forced | 200 | 3.4 s | 1,354 | 0 differing of 1,579 minutes |

Peak 2,917 by both routes at every stage. `cc_minute_delta` was never truncated after the initial
build; it carries 31,094 rows against a rebuild's 28,074 — the difference is cancelling corrective
rows, which merges collapse and correctness never depends on.

**The straggler, concretely.** One heartbeat at `2026-07-26 10:45:10` into a 290 s gap of an
already-published session, 46 minutes behind the newest event and therefore outside `W = 2400 s`
entirely. It bridges the gap, so the session's two runs merge and `interval_start 10:47:33` **ceases
to exist**. Served concurrency moved `283→284`, `356→357`, `452→453` at 10:44–10:46 — exactly the
three bridged minutes — and matched a from-scratch rebuild on all 1,579.

**What one session actually reads**, three runs each on a settled part set:

| Scope | rows read | of `ev_raw` |
|---|---|---|
| unscoped — what a rebuild reads | 905,559 | 100% |
| `IN (subquery over cc_publish_batch)` | 307,766 | 34% |
| + the batch's event-time window ← shipped | 104,640 | **11.6%** |

Not 78 rows, and the ADR should say so plainly. [ADR 0002](0002-order-by-time-bucket-then-platform.md)
puts `toStartOfHour(event_timestamp)` first in `ev_raw`'s key and `video_session_id` third, so a
session lookup prunes only by generic exclusion search. The event-time window is what recovers the
other 2.9×, and it is safe because the window is *provably complete*: a session's first interval
starts at its first event and its last interval ends at or after its last event, so the union of
(published interval span) and (claimed markings' event span) contains every event the session has.

**Per-phase cost of a one-session run:** negate 688 ms, derive 579 ms, **prune 1,465 ms**, emit
684 ms. The lightweight `DELETE` dominates, and it reads nothing — the cost is mutation scheduling.

## Consequences

- **`session_intervals` needs a prune, and that is a mutation per run.** `ReplacingMergeTree` replaces
  a key; it cannot delete one. A re-derivation can legitimately make an `interval_start` vanish, as
  the straggler above does. Without the prune the orphan survives `FINAL` for ever *and* the next
  run's negation would negate deltas that were never published — the error would compound rather than
  sit still. This is the same class of defect as the `ReplacingMergeTree(interval_end)` bug in
  `sql/10_intervals.sql`: a merge rule assuming re-derivation can only ever add. A `DELETE` every
  minute is a known ClickHouse smell; the escape is to make `session_intervals` a view over an
  append-only per-run ledger, which touches tables other agents own and is deliberately not done here.
- **Crash consistency is by phase marker plus dedup token, not by transaction.** The four statements
  are not atomic. `cc_publish_runs` records each phase as it lands and a resumed run continues rather
  than restarting (restarting would negate twice); each heavy statement additionally carries
  `insert_deduplication_token = '<run_id>:<phase>'`, so replaying one that *did* land is dropped by
  the server. Verified on `SharedAggregatingMergeTree` before the design was written. On a
  non-replicated local MergeTree that token needs `non_replicated_deduplication_window > 0`, which
  `cc_minute_delta` does not set — on local, the phase markers alone carry it.
- **One assumption, stated once: `PUBLISH_SETTLE_S`.** A marking is eligible only when it is 5 s old,
  because `now64(3)` is evaluated when an insert *runs* and its rows appear when it *commits*.
  Consuming a marking mid-commit would digest part of an insert and record it as done. This is also
  the floor on publish lag: end-to-end freshness is `SETTLE + batch interval + ~3.5 s`.
- **A scalar cursor is not enough**, and the first evidence run proved it: with a cursor plus a safety
  lookback, every run re-claimed the previous batch entire — 6,659 sessions re-derived to absorb 5.
  Correct, since re-publication cancels, but it turns an incremental update back into a rebuild.
  `cc_publish_consumed` records which INSERTs have been digested (one row per insert — `now64(3)` is
  constant-folded per query, so `marked_at` identifies the insert), which makes the boundary case
  decidable instead of a choice between losing an update and redoing everything.
- **`cc_minute_delta` grows with corrections.** 31,094 rows vs a rebuild's 28,074 after five runs.
  Row count is not a correctness signal — already noted in ADR 0006, now true in the shipped path.
- **The shelved projection deserves a second look, on numbers.** `WALKTHROUGH.md` §5 records
  `proj_by_session` as measured and not shipped, on the grounds that "the actual straggler path uses
  `IN (subquery)`, which full-scans anyway, so the real gain is 1.00× for +94% storage". Re-measured
  on the finalizer's actual shape (PHASE 8): the projection **is** chosen for the `IN (subquery)`
  form on 26.2, taking the one-session read from 104,640 rows to **8,193 (0.9% of `ev_raw`)**, a
  12.8× reduction, for +91% storage (3.73 → 7.16 MiB). The storage trade is unchanged and is still
  the operator's call; the "1.00×" half of it does not hold for this query. **Not shipped here** —
  the finalizer meets its target without it, and reversing another measured decision is not this
  ADR's to make. Note also that `sql/60_projection.sql` hard-codes `sonyliv.` and so cannot be
  applied to any other database (the same defect [ADR 0010](0010-content-views-are-database-agnostic-and-label-their-ambiguity.md)
  fixed in `sql/80_content.sql`); PHASE 8 had to issue the `ALTER` itself.
- **Nothing was applied to `sonyliv`.** The proof runs in `sonyliv_pub` against a control rebuild in
  `sonyliv_pub_ctl`. `make reconcile` on the graded service is unchanged and green: 17,028 minutes,
  0 mismatched, peak 2,917. Going live is one `tools/apply-sql.sh --database sonyliv sql/12_publish.sql`
  plus `tools/publish.sh --database sonyliv --loop 60 PUBLISH_ALLOW_PROD=1`, and it is a human's call.

## The two files this ADR could not edit

`sql/40_deltas.sql` and `tools/build-model.sh` are owned by another agent this round. Neither *needs*
changing — the design works by templating — but both would be cleaner, and the diffs are recorded
here as the constraint requires.

**`sql/40_deltas.sql` — parameterise the source and the sign** so `tools/publish.sh` stops needing
four `sed` anchors, three of which are whitespace-sensitive:

```diff
-INSERT INTO cc_minute_delta
+-- {{TARGET}} defaults to cc_minute_delta; {{SIGN}} to +1. The publisher passes
+-- {{SIGN}} = -1 for the corrective half of a correction-by-diff (ADR 0006/0013).
+INSERT INTO {{TARGET:-cc_minute_delta}}
@@ merged AS
-    FROM session_intervals FINAL
+    FROM {{SOURCE:-session_intervals FINAL}} {{WHERE}}
@@ final SELECT
-    sum(d)  AS delta,
-    sum(op) AS starts,
-    sum(cl) AS ends
+    {{SIGN:-1}} * sum(d)  AS delta,
+    {{SIGN:-1}} * sum(op) AS starts,
+    {{SIGN:-1}} * sum(cl) AS ends
```

`starts`/`ends` are already `Int64` (fixed at `388a845`), so the negative corrective row is
representable and the publisher negates all three rather than zeroing two, which
`tools/truncation-test.sh` still has to do.

**`tools/build-model.sh` — one line, so a rebuild and the publisher do not fight.** A full rebuild
already leaves the tables consistent (it truncates, so there is no `build_version` race), but it
leaves the change log claiming work that the rebuild just did. Without this, the first publish run
after a `make model` on a fresh database re-derives every session — correct, wasteful, and it looks
like the incremental path failing:

```diff
 echo "== 3/3  views"
 TARGET="$TARGET" tools/apply-sql.sh sql/20_views.sql >/dev/null
+
+# A full rebuild has just published everything. Tell the finalizer so, or its
+# next run re-derives the whole file to reach a state it is already in.
+# No-op if sql/12_publish.sql has not been applied. See ADR 0013.
+q "INSERT INTO cc_publish_consumed (marked_at, run_id)
+   SELECT DISTINCT marked_at, 0 FROM session_dirty" 2>/dev/null || true
 echo "   ok"
```
