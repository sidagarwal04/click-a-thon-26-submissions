# ADR 0023 — What a reader is (and is not) guaranteed to see during publication

> **Summary:** A dashboard read landing mid-publish can see the concurrency curve **collapse by up
> to 87.8% for ~13.6 s** (measured: 2,825 → 344, realistic 7,723-session batch, Cloud 26.2.1.525),
> because `negated` appends `-deltas(old)` to the serving table three phases before `emitted`
> appends `+deltas(new)`; the hour and user tiers then lag the minute tier's recovery by a further
> 3.8 s and 7.3 s, disagreeing categorically in between. No gate catches this — every gate runs
> *between* publishes. Fix: stage both corrections and give `cc_minute_delta` ONE insert
> (prototyped: 0 deviating samples, 79 ms, one part). Cross-tier `generation_id` gating is
> REJECTED **for the publisher** — it is incompatible with the ReplacingMergeTree tiers *while the
> generation is a payload column*; moving it into the sort key removes that objection and is what
> [ADR 0034](0034-generation-pinned-serving-surface.md) does for the **rebuild** path. Status:
> accepted 2026-08-02; the fix is **handed off**, not applied (see Consequences). Evidence:
> `evidence/publish-visibility/`. Closes Codex 003 §7.3.5/§7.3.9 (finding → contract + fix design).

**Status** Accepted · 2026-08-02 · amends [ADR 0013](0013-continuous-publication-by-incremental-finalizer.md)
and [ADR 0016](0016-publisher-owns-the-user-and-hour-tiers.md); answers Codex audit §7.3.5 and
§7.3.9 (`docs/codex-validation/003.md`), triaged as "genuinely new and unowned" items 1–2 in
`docs/codex-validation/003-triage.md` §D. The implementation is deliberately **not** applied here —
`tools/publish.sh` and `sql/12_publish.sql` are owned by the publisher-state-machine-safety work
(queue Q8–Q11); the handoff section below says exactly what should change once that merges.

## Context

ADR 0013's finalizer publishes a batch in phases: `claimed → negated → derived → pruned → emitted`,
and since ADR 0016 also `→ hours → users → committed`. Correction-by-diff is *algebraically* exact —
`-deltas(old) + deltas(new)` converges to the rebuild answer — but the two halves of that correction
are **separate inserts into the live serving table**, with the whole derive/prune machinery between
them. Codex 003 observed (§7.3.5) that a reader landing between `negated` and `emitted` sees the
claimed sessions' entire contribution *missing*, and (§7.3.9) that the minute, hour and user tiers
are updated at three different points in the run, so cross-tier reads can disagree.

Neither our convergence harness (`tools/publish-test.sh`, 16 checks) nor `/reconcile` could ever
see this: both read the serving tables **between** publish runs, when the algebra has already
closed. The vulnerable state exists only *during* a run. This ADR is the result of deliberately
reading during one.

Everything below was measured on Cloud 26.2.1.525 in scratch database `sonyliv_q29vis` (the graded
database was read-only source data throughout); scripts and raw samples are in
`evidence/publish-visibility/`.

## What was measured

**1 · The dip is real, and it is exactly the claimed sessions' contribution.** Force-republishing
300 *unchanged* sessions covering probe minute `2026-07-26 10:54` (true value 2,825, never moves)
dropped the served minute-tier value to **2,525 — exactly −300 —** for every poll sample between
the `negated` write becoming visible (17:42:47.429) and the `emitted` write becoming visible
(17:42:58.808): a **window of 11.38 s**. The dip is not noise and not partial: statement-level
insert visibility means the negation lands whole, so a covered minute loses the *full* contribution
of every claimed session covering it.

**2 · At realistic batch size the dip is catastrophic, not cosmetic.** Landing the remaining stream
(7,723 sessions — the shape of a catch-up run after an outage, or the unseen day's first publish
after bootstrap) dropped the same probe minute from 2,825 to **344 (−87.8%) for 13.6 s**. A
dashboard user watching the headline curve during that window sees national concurrency collapse
and recover; an alert keyed on a sudden drop would fire.

**3 · The window is mostly our own bookkeeping, but its floor is real.** Of the 13.6 s, only
~2.5 s is ClickHouse statement time (`derive` 1.04 s + `prune` 1.03 s + `emit` 0.45 s). The other
~11 s is `tools/publish.sh` between-phase overhead — chiefly `written_rows()`, which runs
`SYSTEM FLUSH LOGS` after every phase (seconds each on Cloud), plus phase-marker inserts and HTTP
round trips. Trimming the bookkeeping would shrink the window to roughly the derive+prune time
(~1.3–2.1 s at this scale, growing with batch size) — **narrower, but never zero, because `emit`
must wait for `derive` and `prune` by construction** (it reads `session_intervals FINAL`).

**4 · ADR 0016's phases do not widen the dip; they add a second, different exposure.** `hours` and
`users` run *after* `emitted`, so the minute-tier dip is unchanged by them. What they add is
**cross-tier lag**: after the minute tier recovered at 17:45:18.844, the hour tier still served the
pre-batch state until 17:45:22.6 (**+3.8 s**) and the user tier until 17:45:26.1 (**+7.3 s**). At a
minute inside the incoming data (probe B, 11:30) the disagreement is categorical, not marginal:
minute tier says 197 concurrent, hour tier has **no row at all** for the hour, user tier says 0.
Before ADR 0016 those tiers were not updated by the publisher at all — stale indefinitely — so
bounded lag is strictly better; but "bounded" is now a number, and this ADR records it.

**5 · The one-block fix kills the dip, cheaply.** Experiment 3 re-ran the forced batch with the
phase order changed: negation staged into a scratch table, derive and prune as today, new deltas
staged, then **one** `INSERT INTO cc_minute_delta SELECT … FROM stage` carrying both signs.
The racing poller saw **0 deviating samples**. The swap took **79 ms**, and `system.part_log`
shows it produced **one part** — with `optimize_on_insert` (default on) collapsing the ±pairs
inside the insert block before the part was written (2,440 rows in, 1,220 stored). Total staging
overhead added to the run: two staged inserts of ~200 ms each; the swap replaces the old emit.

## Decision

**1 · The minute-tier correction becomes one insert (Codex §8.3 minimum fix) — recommended,
handed off.** The `negated` and `emitted` phases stop writing `cc_minute_delta` directly; both
corrections accumulate in a per-run staging table and land in a single INSERT after `pruned`. The
prototype proves the mechanism and the cost. This changes the phase list, so it belongs to the
publisher-safety work now rewriting that state machine — the handoff below is the specification.

**2 · Cross-tier atomicity is NOT pursued. The lag is documented, bounded, and labeled instead.**
A `generation_id` that exposes only committed generations — Codex's stronger option — is rejected
for this system (analysis below). The cross-tier contract is: *tiers may disagree for up to ~8 s
after a batch (measured; scales with tier size, not history), and the only coherent-read guarantee
is between runs.* `v_cc_publish_lag.runs_in_flight` is already the tell a dashboard can use; the
handoff includes exposing per-tier commit markers so the label can be per-tier.

**3 · The visibility contract below becomes the reference.** Anything that serves these tables —
dashboards, the bench harness, the unseen-day runbook — should cite it rather than assuming
serving reads are always coherent.

## The visibility contract

What a reader **is** guaranteed:

- **Between publish runs** (`runs_in_flight = 0`): every tier is exact (convergence proven to 0
  differing cells against a from-scratch rebuild, ADR 0013/0016) and mutually coherent.
- **Eventually**: every run converges; nothing a reader observes mid-run survives the run.
- **Statement atomicity per part**: a single insert's rows in one partition land together (our
  batch inserts are far below `max_insert_block_size`, so in practice one part per touched day
  partition). A reader never sees half of one insert's rows *within a partition*.
- **Signedness is honest**: the serving views deliberately do not clamp negatives, so a broken
  (as opposed to in-flight) delta model shows up loud rather than being masked.

What a reader is **not** guaranteed — the half that matters:

- **During a run, today**: any minute covered by a claimed session's published intervals reads LOW
  by that session's full contribution, from the moment `negated` commits until `emitted` commits.
  Measured: 11.4–13.6 s; worst measured magnitude −87.8%. With the one-block fix: this clause
  deletes entirely for the minute tier.
- **Cross-tier, during and shortly after the minute swap**: minute, hour and user tiers may
  reflect three different publication points for ~4–8 s (measured; the `hours` phase cannot be
  hoisted before the swap because it reads `cc_minute_delta` itself). Disagreement can be
  categorical — a minute-tier value with no corresponding hour row. The one-block fix does NOT
  change this clause; only its start point moves (dip end → swap).
- **No in-band marker**: rows carry no generation stamp, so a reader cannot tell from the data
  alone whether it is reading mid-run. The out-of-band tell is `v_cc_publish_lag.runs_in_flight`.
- **Multi-day batches**: the one-block insert commits per partition (day). A batch spanning D days
  lands as up to D parts. Deltas are hour-clipped and every serving running-sum is partitioned by
  hour, so no *served value* mixes two partitions — but a reader scanning a multi-day range in the
  swap's few-ms commit window could see day X corrected and day Y not yet. At 100×, an insert
  exceeding `max_insert_block_size` (1M rows) would additionally split within a partition;
  `min_insert_block_size_rows` on the swap, or accepting the per-partition bound, covers this.
  State it; do not pretend the insert is globally atomic.

## Why `generation_id` is rejected

> **SUPERSEDED FOR THE REBUILD PATH, 2026-08-02 — see
> [ADR 0034](0034-generation-pinned-serving-surface.md).** Item 3 below is correct *and* incomplete:
> FINAL-before-WHERE breaks a generation filter only while `generation` is a **payload** column.
> Move it into the ORDER BY and rows of different generations are different keys, so FINAL has
> nothing to collapse across — reproduced both ways in
> `evidence/generation-pinning/10-final-vs-where.txt` (payload → 0 rows returned; key column → the
> committed row, every time). ADR 0034 builds the pinned surface on that placement and measures its
> cost at +0.0% rows read and +1.4–5.8 ms/query. What stands unchanged is the rejection **for the
> publisher**: a per-publish generation means copying every tier per batch, which is not
> affordable, so the one-block correction below is still the right fix for the dip. Items 1 and 2
> below are still the honest cost of a pinned read, and ADR 0034 measures them rather than
> estimating them.

The proposal: stamp every published row with a generation, expose `committed_generation` from the
runs log, and make every serving view filter `WHERE generation <= committed`. Three costs, the
third structural:

1. **Every serving view changes and every read pays a subquery** against the runs log — on the hot
   dashboard path, for a window that is ~13 s per run today and ~0 with the one-block fix.
2. **The additive tier could carry it** (`cc_minute_delta` is append-only; an uncommitted
   generation's rows are cleanly excludable) — but with the one-block fix the minute tier no longer
   needs it: there is nothing mid-run to hide.
3. **The Replacing tiers cannot carry it without redesign.** `cc_hour_agg` and `cc_user_minute` are
   `ReplacingMergeTree(computed_at)` read through FINAL — and FINAL resolves *before* WHERE. An
   uncommitted newer row does not sit invisibly behind a filter: it **replaces** the committed row
   at read time, and the generation filter then discards the survivor, leaving *no row* — worse
   than the lag it was meant to hide. Gating these tiers means abandoning FINAL for argMax-over-
   version reads or double-writing shadow tables, i.e. re-litigating ADR 0016's engine choice —
   ClickHouse offers no multi-table transaction to buy coherence outright (Codex §8.3 says the
   same: "must not be assumed").

What replaces it: the lag is small, bounded, and *labelable*. A per-tier commit marker (phase rows
already exist in `cc_publish_runs`) lets any dashboard print "hour tier as of run N−1" during the
window. Honesty at ~zero cost, versus atomicity at a redesign.

Also considered and set aside:

- **Hoisting `users` before the swap** (it reads only `session_intervals`, so it *could* run
  earlier): this just flips the sign of the incoherence — user tier ahead of minute tier instead of
  behind — and removes nothing. Rejected.
- **Pre-staging the hour/user re-derivations too**, then firing the three tier inserts
  back-to-back: shrinks cross-tier lag from ~8 s to roughly one insert's commit time (~1 s),
  at the cost of two more staging tables and a `hours` derivation rewritten to read
  post-swap-state-from-staging instead of `cc_minute_delta`. Legitimate follow-on if the ~8 s
  window ever matters at the grains we serve; not part of the minimum fix.

## Handoff — what should change, once the publisher-safety work merges

Owned by the `docs/publisher-state-machine-safety` branch; do not apply concurrently. Prototype to
crib from: `evidence/publish-visibility/30-oneblock-fix.sh`.

**`sql/12_publish.sql`:**

1. Add a per-run staging table, e.g. `cc_publish_stage` — same columns as `cc_minute_delta` with
   plain `Int64` measures, plus `run_id`; `PARTITION BY run_id`, TTL like `cc_publish_batch`.
   Per-run partitioning is what makes a crashed run's staging droppable and a resumed run's
   staging replayable.
2. Update the phase list comment: `claimed → staged_neg → derived → pruned → staged_pos →
   swapped → hours → users → committed`.

**`tools/publish.sh`:**

1. `negate` phase: same templated SQL, but `INSERT INTO cc_publish_stage` (one extra sed
   substitution on the `INSERT INTO cc_minute_delta` line — the prototype shows it) with the
   run_id column added; phase marker `staged_neg`.
2. `emit` phase likewise → `staged_pos`.
3. New `swap` phase after `staged_pos`:
   `INSERT INTO cc_minute_delta SELECT <cols> FROM cc_publish_stage WHERE run_id = <run>` with
   `insert_deduplication_token = '<run>:swap'` — the only write the serving table sees. Then
   `ALTER TABLE cc_publish_stage DROP PARTITION <run>` at commit (or leave to TTL).
4. Crash model is preserved, not weakened: staging inserts carry their own dedup tokens
   (`<run>:staged_neg` / `<run>:staged_pos`) so a resumed phase that already landed is dropped by
   the server, same as today; the swap is idempotent by its token; a run that dies pre-swap has
   written **nothing** to the serving table — which is strictly better than today, where a crash
   between `negated` and `emitted` leaves the dip *persisted* until resume (today's crash-window
   exposure is the dip made durable; the fix removes that class entirely — worth stating in the
   Q8–Q11 work's ADR).
5. Consider dropping the per-phase `SYSTEM FLUSH LOGS` (move `written_rows` reads to a single
   post-commit pass): it is ~10 s of the ~13 s window today and would still be worth removing
   *after* the fix, since it stretches the cross-tier window too.

**Acceptance:** re-run `evidence/publish-visibility/10-dip-forced.sh` (pointed at a scratch db
built by the new publisher) — the poller must show 0 deviating samples; `tools/publish-test.sh`
stays green on all 16 checks; `system.part_log` for the swap shows parts only in touched
partitions.

## Consequences

- The dip stops being an unknown: it has a magnitude (up to −87.8% measured), a window
  (11.4–13.6 s today; floor ~2 s without bookkeeping; 0 with the fix), and an owner.
- The cross-tier lag is accepted and documented (~4–8 s, bounded by tier re-derivation time, not
  history), with a labeling path instead of an atomicity promise. Anything presenting mixed-tier
  dashboards during live publishing should read `v_cc_publish_lag` and say so.
- The graded database is unaffected: its publisher has never committed a run, and nothing in this
  ADR was applied there. The scratch database `sonyliv_q29vis` is disposable
  (`DROP DATABASE IF EXISTS sonyliv_q29vis`).
- Codex 003 §7.3.5/§7.3.9 move from "genuinely new and unowned" to "measured, designed, handed
  off". §8.3's minimum fix is confirmed *actually cheap* (79 ms swap, ~400 ms staging, one part);
  its stronger option is rejected with a structural reason, not a shrug.
