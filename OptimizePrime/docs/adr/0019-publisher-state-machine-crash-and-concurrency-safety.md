# ADR 0019 — The publisher's state machine becomes crash-safe and single-writer, and says what it still cannot promise

> **Summary:** Four defects in the ADR 0013/0016 publisher, all REPRODUCED before fixing: (Q8) a crash
> between the consumed-insert and the `claimed` mark orphaned the batch forever with every monitor
> reading healthy, and a resume after `derived` recomputed `build_version` so the prune deleted the
> crashed run's own derivation — a session vanished from all four tiers; (Q9) two concurrent publishers
> both claimed the same marking and served `2X′−X` (one viewer counted twice, both runs green); (Q10)
> `cc_publish_consumed` keyed on `marked_at` alone suppressed the slower of two same-millisecond inserts
> permanently. Fixes: a `claiming` intent row + rollback sweep, BV recorded at claim and reused on
> resume, a lease with deterministic tiebreak + per-phase fencing, the `(marked_at, insert_id)` pair
> identity via `initialQueryID()`, and retention-headroom columns in `v_cc_publish_lag` (Q11). The
> crash matrix then caught a FIFTH defect: `insert_deduplication_token` does not drop a replayed
> INSERT SELECT (measured — both executions wrote rows), so negate/emit replays are decided from
> `system.query_log` instead. Status: accepted, 2026-08-02. Proven by `tools/publish-test.sh`
> PHASES 12–15; nothing run against `sonyliv`.

**Status** Accepted · 2026-08-02 · amends [ADR 0013](0013-continuous-publication-by-incremental-finalizer.md)
and [ADR 0016](0016-publisher-owns-the-user-and-hour-tiers.md) — closes the crash/concurrency
invariants ADR 0016's consequences listed as "inherited, not fixed" (Codex audit §4.3–4.5, queue Q8–Q11)

## Context

ADR 0013 built the finalizer around phase markers and `insert_deduplication_token`, and ADR 0016
extended the chain to seven phases. Both recorded the same honest caveat: the claim window, the
single-publisher assumption and the `marked_at` identity were unexamined. The Codex audit turned the
caveat into four concrete defects. All four came from code inspection; the brief for this change
required reproducing each before fixing it, and all four **did reproduce** on Cloud 26.2.1.525
against a scratch database (70,830-event slice, 467 sessions — small enough to iterate, real enough
to publish):

- **Q8a — the pre-`claimed` crash window.** The claim ran batch-insert → consumed-insert → `claimed`
  mark. Killing the process between the last two left the markings recorded as digested by a run that
  never registered. Reproduced outcome: `tools/publish.sh` next run printed `nothing to publish`,
  `v_cc_publish_lag` read `pending_sessions = 0, runs_in_flight = 0`, and the serving tiers were
  empty. The batch was gone and **the monitoring said healthy** — the pending count used the same
  suppressed predicate that caused the loss.
- **Q8b — resume recomputed `build_version`.** The resume path re-derived `BV` as
  `greatest(now, max(build_version)+1)`. A run crashed after the `derived` mark resumed with a
  *fresh, larger* BV, so `pruned`'s `DELETE … build_version < BV` deleted both the superseded rows
  **and the crashed run's own derivation**. Reproduced outcome: the session's interval count went
  3 → 0, its negation rows stood with no re-emission, and it vanished from all four tiers — every
  status line green.
- **Q9 — no mutual exclusion.** "Find in-flight, then claim" has a window in which a second
  publisher sees no in-flight run and unconsumed markings. Reproduced with two staggered publishers
  (fault-injected holds): both claimed the same marking under different `run_id`s, both negated the
  same published contribution `X`, both emitted `X′`. Served result `2X′−X`: probe minute went
  15 → 17 where the true answer was 16. **Both runs committed cleanly.** Worse, the state is
  unrepairable by the publisher itself — a later correction appends `−FINAL + FINAL′ = 0` net, so
  the excess persists until a full rebuild.
- **Q10 — `marked_at` is not an identity.** `cc_publish_consumed` was keyed on `DateTime64(3)`
  alone. Two same-millisecond inserts where the slower one commits later: the fast one is consumed,
  and the slow one's marking then matches the consumed set and is skipped forever. Reproduced (MV
  detached to make the slow insert's visibility genuinely late): the event was never published and
  `pending_sessions` read 0.
- **Q11 — retention as an unenforced bound.** `session_dirty`, `cc_publish_batch` and
  `cc_publish_consumed` carry 7-day TTLs. A TTL on a queue is a deadline: work that outlives it
  expires silently. Not a race to reproduce but a bound to instrument — and it interacts with Q10's
  fix (see the lookback below), which makes the missing signal load-bearing.

## Decision

**1 · The claim writes intent first, and anything before `claimed` rolls back (Q8a).** A new first
phase `claiming` is appended to `cc_publish_runs` *before any side effect*, so no consumed row and no
batch partition can exist without a run row naming them. The claim order becomes: intent → consumed
→ batch → `claimed`. A recovery sweep (`recover_claims`, run under the lease before every batch)
rolls a run whose latest phase is `claiming` **back** — its consumed rows deleted, its batch
partition dropped, the run marked `aborted` — because nothing after `claimed` can have run, so
undoing the claim is exact and the markings become claimable again. Runs at `claimed` or beyond roll
**forward** (resume), as before. The sweep also deletes consumed rows and batch partitions whose
`run_id` appears nowhere in the runs log: that is exactly the Q8a debris a pre-0019 crash left, so
adopting this version heals an already-orphaned database instead of merely not adding to it.

**2 · The batch derives from the consumed set, not beside it.** The consumed-insert is now the one
statement that reads the queue; the batch-insert selects the pairs recorded under this `run_id`.
With two independent queue reads, a marking surfacing between them would be recorded as digested yet
never claimed — Q10 through the side door. One read, then a join, closes it.

**3 · `build_version` is allocated once and recorded in the `claimed` mark (Q8b).** Resume parses
`bv=` back out of the run's notes and reuses it, which makes the re-derive replay-identical (the
dedup token then actually matches) and makes the prune delete only genuinely superseded rows. For a
legacy run with no recorded BV, resume at `claimed`/`negated` allocates fresh (nothing derived yet);
at later phases it recovers the BV from the batch scope's own max, and refuses to guess if it cannot.

**4 · A lease makes the publisher single-writer per database (Q9).** ClickHouse has no server-side
compare-and-set, so `cc_publish_lease` builds exclusion from what it does have — atomic
visible-or-not INSERT — plus a deterministic tiebreak: decline if a live lease exists; otherwise
insert an owner row, wait out the visibility window (the same settle assumption the marking queue
already makes), and let every observer compute the same winner — greatest `(acquired_at, owner)`
among live rows, on the server's clock. Newest-wins is deliberate: a new acquirer can only exist
after the old lease expired, so a revived zombie must lose to its replacement rather than steal the
run back. The holder **renews and re-checks before every write phase** (`lease_beat`); losing the
lease aborts before the next statement, and the next holder resumes the run from its markers with
the same `run_id`, tokens and BV. All lease reads run with `select_sequential_consistency = 1` so
SharedMergeTree replicas cannot serve a stale live-set. `run_id` allocation also became
collision-proof under the lease: `greatest(epoch_ms, max(run_id)+1)` server-side.

**5 · The insert identity is the pair `(marked_at, insert_id)` (Q10).** `mv_session_dirty` now
captures `initialQueryID()` — verified constant-folded per query on 26.2.1.525 (legal alongside
`GROUP BY`, one value across groups, distinct across inserts) — and `cc_publish_consumed` is keyed
`(marked_at, insert_id)`. `marked_at` stays first so the cursor-range read stays a prefix scan. The
settle rule still makes the same-millisecond race improbable; the pair makes it unambiguous when it
happens anyway.

**6 · The claim gains a bounded lookback, made safe by the pair identity.** An insert that outlives
the settle window surfaces a marking already behind the committed cursor; without a lookback it
would never be scanned again. The claim now scans `[cursor − PUBLISH_LOOKBACK_S, cursor_to]`
(default 900 s). This is exactly the "fuzzy window" ADR 0013 rejected — and it is safe now for the
reason it was not then: exactness lives in the consumed *set*, so re-scanning re-claims nothing
(the 6,659-sessions-re-derived-to-absorb-5 pathology cannot return).

**7 · Retention becomes a measured headroom, not a hope (Q11).** `v_cc_publish_lag` gains
`retention_ttl_s`, `oldest_pending_age_s`, `retention_headroom_s` and `retention_alert` — the age of
the oldest **undigested** marking (pair identity, `minOrNull` so an empty queue reads NULL rather
than a 56-year breach) against the 7-day TTL, with the alert tripping a day early. This is a view
change only: per the brief, `docs/OBSERVABILITY.md` and the `sonyliv observe` emitter are another
agent's files — the intended wiring is to emit `retention_alert`, `retention_headroom_s` and
`pending_sessions` as gauges next to the existing watermark-lag signal, and alert on
`retention_alert = 1` or on `publish_lag_s` growing monotonically across scrapes.

**8 · The publisher refuses a half-migrated schema.** `preflight_schema` checks five facts (the two
`insert_id` columns, the pair sort key, the MV capturing `initialQueryID`, the lease table) and dies
with the migration commands otherwise. Migration is documented in `sql/12_publish.sql`: drop
`mv_session_dirty` + `cc_publish_consumed`, re-apply the file (an `ALTER … ADD COLUMN IF NOT EXISTS`
heals `session_dirty` in place). Forgetting the consumed set re-claims TTL-window markings once —
a no-op by idempotence (PHASE 8), not a correctness event.

## The safety ledger — what holds, and by what mechanism

**Atomic** (single statements, visible-or-not): each phase's INSERT/DELETE; the intent mark; lease
rows. Nothing else is atomic — the run as a whole never is, which is why everything below exists.

**Idempotent** (safe to repeat): the derive (same rows at the same pinned BV — Replacing absorbs
the duplicate; before this ADR the resumed derive was *not* the same statement); the prune
(`DELETE … < BV`); the hours/users re-derivations (rewrite the same row at a newer version);
republication of an unchanged session (`−X + X = 0`, PHASE 8); the rollback sweep (deleting
already-deleted rows and dropping already-dropped partitions are no-ops).

**NOT idempotent, and no longer pretending to be: negate and emit.** ADR 0013 attached
`insert_deduplication_token` to every heavy statement as belt-and-braces against replays. The crash
matrix **measured that belt broken**: on Cloud 26.2.1.525 a replayed `INSERT SELECT` into the
`SharedAggregatingMergeTree` delta table executed both times — `system.query_log` recorded two
`QueryFinish` entries for the same query_id, each with `written_rows > 0` — and the served number
double-counted the correction by exactly one viewer (the matrix's convergence check caught it; the
original ADR 0013 verification evidently used a different insert shape). A resumed run therefore
decides negate/emit replays from the server's own record (`stmt_landed`): wait until the query_id
is no longer in `system.processes` — a crashed *client* does not stop a statement already running
server-side — flush logs, and treat a recorded successful finish as "landed, do not re-issue". The
tokens stay attached, but nothing load-bearing rests on them.

**Fenced** (cannot run without currently holding the lease): the *decision to issue* every write
phase, via `lease_beat` = renew + re-check winner. The recovery sweep and the claim run under the
same fence.

**Still NOT guaranteed** — the section that matters:

- **A statement already in flight when its issuer loses the lease is not fenced.** The fence is
  checked before issuing, not inside the server. A holder that stalls *mid-statement* past the TTL
  can have its statement land concurrently with the new holder's work. The blast radius is bounded,
  not eliminated: the new holder resumes the same `run_id` with the same BV, so derive/prune/hours/
  users overlaps collapse to the same writes, and for negate/emit `stmt_landed` *waits* for the
  zombie's query_id to leave `system.processes` before deciding — so the specific
  landed-then-replayed shape is closed. The residual exposure is a zombie statement that has not
  yet *started* server-side when the new holder checks (client sent, server not yet registered):
  vanishingly narrow, not reproducible on demand, and accepted as a bounded risk. Mitigation if it
  ever matters: per-statement fencing tokens in a `WHERE` clause, at the cost of putting the lease
  table on every hot path.
- **The settle bound is still an assumption.** `PUBLISH_SETTLE_S` (markings) and
  `PUBLISH_LEASE_SETTLE_S` (lease lottery) both assume an insert's rows are visible within the
  window. The lookback + pair identity now make a *marking* that violates it recoverable (it is
  claimed late, exactly once); a *lease row* that violates it can admit two winners for one
  lottery — the TTL and per-phase re-checks shrink that window but do not close it.
- **An insert delayed beyond the lookback is not claimed.** It surfaces only through
  `retention_alert`/`pending_sessions`; the repair is a forced republication (`--sessions`) or a
  rebuild, both idempotent. Widening `PUBLISH_LOOKBACK_S` trades scan width for tolerance.
- **Wall-clock leases.** Lease liveness compares server-written timestamps against server `now()`,
  so a *server-side* clock jump degrades to the TTL bound; publisher-host clocks are irrelevant
  (all times are the server's). This is a lease, not a consensus protocol, and one ClickHouse
  service is the single arbiter.
- **`cc_publish_runs` is unbounded.** One intent row per non-empty tick plus one per phase. The
  idle-tick pend-check keeps empty ticks out of it, but a busy service grows it; it is the audit
  trail, so no TTL was added deliberately. Revisit if it ever dominates.

## What the harness now proves (PHASES 12–15, `evidence/publish.txt`)

- **PHASE 12 — crash matrix.** Sixteen injection points (`PUBLISH_CRASH_AT`): after every phase mark
  *and* after every heavy statement before its mark — the two ADR 0016 phases included. Each round:
  append a +30 s beat to a synthetic heartbeat-only probe session, crash there, wait out the dead
  holder's lease, run recovery, assert the published end advanced exactly +30 s with zero in-flight
  runs and zero pending sessions; full four-tier convergence against the from-scratch control after
  all sixteen. The probes are synthetic of necessity — every real session carries a
  `VideoSessionEnd`, and a beat injected after a closer is absorbed *without* extending coverage
  (ADR 0007/0009), so no real session can carry a deterministic "+30 s" assertion.
- **PHASE 13 — two publishers.** One held mid-claim by fault injection, one started 2 s later:
  exactly one commits, one declines, the probe minute moves by exactly one viewer (the pre-lease
  reproduction moved it by two), and all four tiers converge.
- **PHASE 14 — same-millisecond identity.** Two markings stamped the same `marked_at`; the fast one
  consumed; the slow one's event inserted with the MV dropped (its marking is the only path to the
  event) and its marking landed after consumption. The pair identity claims it; the end advances.
- **PHASE 15 — retention headroom.** A 6.5-day-old marking trips `retention_alert = 1`, is
  correctly *not* claimed (beyond the lookback — the alert, not the claim, is the repair path),
  and clearing it resets the alert.

## Consequences

- **`tools/publish.sh` grew fault-injection hooks** (`PUBLISH_CRASH_AT`, `PUBLISH_SLEEP_AT`) — inert
  unless set, and the crash hook deliberately does not release the lease, so tests recover the
  honest way. Tunables: `PUBLISH_LOOKBACK_S` (900), `PUBLISH_LEASE_TTL_S` (60),
  `PUBLISH_LEASE_SETTLE_S` (2).
- **A second publisher invocation now exits 0 with a "declining" message.** Loop-mode deployments
  gain redundancy semantics for free: run two `--loop` publishers and one works while the other
  breathes; if the worker dies, the survivor takes over within one TTL.
- **The graded database is untouched.** `sonyliv` still has the pre-0019 objects (its publisher
  cursor sits at epoch; it has never committed a run). If the publisher is ever pointed at it, the
  preflight will demand the documented migration first.
- **Cross-references owned by other agents** (not edited here, per worktree ownership): ADR 0013/0016
  carry consequence lines describing Q8–Q10 as open — they are now closed by this ADR;
  `docs/OBSERVABILITY.md` should gain the three gauges from decision 7; `docs/TESTS.md` should list
  PHASES 12–15; `docs/WORKTREE_QUEUE.md` should mark Q8–Q11 done.
- **Runtime cost of safety:** one intent insert + one lease renewal/check per phase (~7 small
  queries per run) and the recovery sweep's three lookups per batch. Measured noise against the
  0.5–2 s phases. `publish-test.sh` runtime grows by ~10 minutes, almost all in the crash matrix.
