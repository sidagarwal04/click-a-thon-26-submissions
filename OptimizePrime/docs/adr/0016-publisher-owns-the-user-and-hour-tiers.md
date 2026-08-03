# ADR 0016 — The publisher owns the user and hour/day tiers, and the user tier becomes replaceable

> **Summary:** ADR 0013's finalizer maintained only `session_intervals` and `cc_minute_delta`, so
> minute totals stayed current while `cc_user_minute` inflated (a `uniqExact` set union cannot
> retract) and `cc_hour_agg` served stale peaks (Codex audit §4.1, queue Q2). Two new publisher
> phases fix both: `hours` re-derives the touched hours (a plain superseding INSERT — the cube was
> already `ReplacingMergeTree(computed_at)`); `users` re-derives the touched (minute, dims) buckets
> into `cc_user_minute`, REBUILT as `ReplacingMergeTree(computed_at)` with `mv_user_minute` retired,
> because replacement is the cheapest representation in which retraction exists at all. Measured:
> all four tiers converge to a from-scratch rebuild — 0 differing cells across bootstrap, growth,
> shrink, dimension change, a 46-minute straggler and 200 forced republications. Status: accepted,
> 2026-08-01. Proven in `evidence/publish.txt`; nothing applied to `sonyliv`.

**Status** Accepted · 2026-08-01 · amends [ADR 0013](0013-continuous-publication-by-incremental-finalizer.md);
closes the tier half of Codex audit §4.1; extends [ADR 0012](0012-rebuild-owns-every-tier-and-the-last-any-leaves.md)'s
"the rebuild owns every tier it invalidates" to the incremental path

## Context

`tools/publish.sh` (ADR 0013) proved correction-by-diff exact for the minute path and stopped
there: `sql/12_publish.sql` and `tools/publish.sh` contained zero references to `cc_hour_agg` or
`cc_user_minute`. `tools/publish-test.sh` could not see the omission because its scratch databases
never instantiated either table. The failure modes are not symmetric:

- **The hour tier goes stale, boringly.** `cc_hour_agg` is `ReplacingMergeTree(computed_at)` keyed
  on (dims, hour); nothing re-derived touched hours, so `v_concurrency_hour*` and `v_concurrency_day*`
  kept serving the pre-arrival answer. This had already happened once at batch scope — 2,887 served
  against 2,917 real — which is why ADR 0012 made the *rebuild* own the tier. The incremental path
  repeated the same omission.
- **The user tier goes wrong, monotonically.** `mv_user_minute` merged
  `AggregateFunction(uniqExact)` states by SET UNION on every insert into `session_intervals`. Union
  has no inverse: the MV could ADD a user to a (minute, dims) bucket but never RETRACT one whose
  only covering interval shrank, changed dimension tuple, or ceased to exist. That is why
  `tools/build-model.sh` had to TRUNCATE the table on every full rebuild (measured cost of not
  doing so: served 2,953 vs true 2,844, ADR 0012). "Fire the MV again" is not a fix — the
  *representation* cannot express the correction.

## Decision

**1 · The user tier's representation changes: buckets are replaced, never unioned.**
`cc_user_minute` becomes `ReplacingMergeTree(computed_at)` with the `uniqExact` state as a payload
column (verified on Cloud 26.2.1.525 before writing this: the engine accepts the column, FINAL
keeps the newest version per key, and a bucket re-inserted with fewer members reads back smaller).
`mv_user_minute` is retired outright, not adapted: an incremental MV sees one inserted block and
would write a PARTIAL state, and under replace semantics the newest write wins — a partial state
would silently erase a complete bucket. Exactly two callers may write the table, both running the
one canonical INSERT in `sql/45_user_concurrency.sql`: the publisher (scoped to a batch's touched
minutes) and the rebuild (whole, after TRUNCATE).

**2 · Retraction is an explicit empty write, not an absence.** The canonical INSERT unions two
branches: current coverage (expanded from `session_intervals FINAL`, `covered = 1`) and every
bucket key already in the table (`covered = 0`, contributing nothing). A bucket whose coverage
vanished therefore still gets a row — an EMPTY `uniqExact` state at a newer version — which is what
supersedes the stale members. The hour tier gets the same property for free: cancelled deltas keep
the GROUP alive, so a fully-retracted hour re-derives as an all-zero row. The serving views filter
empty/all-zero rows, so "no concurrency" serves as no row — the same answer a fresh rebuild gives.

**3 · Two new phases, after `emitted`, before `committed`:** `hours` templates the canonical
`sql/50_hour_agg.sql` INSERT with an hour scope (legal because deltas are hour-clipped, ADR 0003 —
an hour is self-contained); `users` templates the canonical `sql/45_user_concurrency.sql` INSERT
with a minute scope plus an interval prefilter. Both statements are CUT out of their files between
`PUBLISH_EXTRACT` markers, not reimplemented — the same no-drift rule ADR 0013 set for the
derive/delta SQL. Both carry `insert_deduplication_token`, are recorded in `cc_publish_runs`, and
are idempotent under replay (a re-derivation writes the identical row at a newer version), so they
inherit ADR 0013's resume-by-phase-marker crash model without adding a non-idempotent step.

**4 · The scope is a provable superset, derived from the claim window.** For a batch, every OLD
interval lies inside `[lo, hi]` (ADR 0013's completeness argument: a session's published span and
its claimed markings' event span jointly contain every event), every NEW interval ends by
`hi + TAIL_S`, and a close delta lands at most one minute later. So hours(lo … hi+2h) and
minutes(lo … hi+4min), unioned per session from `cc_publish_batch`, cover everything the batch can
have touched. Over-coverage is deliberately cheap: re-deriving an untouched bucket rewrites the
identical row at a newer version. Buckets are recomputed IN FULL — all sessions covering them, not
only the batch's — because replacement discards the old state entirely; that is the price of
having retraction, and it is bounded by the time window, not by history.

## The options weighed for the user tier, with numbers

The brief was right that this is not a missing INSERT. Three ways to make a distinct count
correctable, measured on the provided file (905,558 events, 10,866 sessions, 9,618 users,
91,692 buckets):

| Option | Storage grain | Write cost per correction | Read cost per query | Verdict |
|---|---|---|---|---|
| **A · Replaceable buckets** (chosen): `ReplacingMergeTree(computed_at)`, publisher recomputes touched buckets in full | 91,692 bucket rows (unchanged) | one-session (straggler) run: 661 ms wall, reading 253.75K rows / 12.30 MiB, 239 ms server-side — window-bounded, not history-bounded | unchanged — `uniqExactMerge` over FINAL, still one state per bucket | **shipped** |
| B · Retractable representation: signed (minute, dims, user) rows, distinct = users with net sign > 0 | ≥ 139,804 per-user rows (1.52× the buckets) *growing with every correction*, since retraction appends | comparable to A (must still derive old + new coverage) | every read becomes GROUP BY user HAVING sum > 0 — a two-level aggregation on the hot dashboard path, and `-1` rows are unmergeable tombstones forever | rejected — pays at read time, forever, for what A pays once at write time |
| C · Periodic reset: keep the union MV, TRUNCATE + full backfill on a timer | 91,692 rows | full backfill = 1.8 s at this scale, O(history) every period | unchanged | rejected as primary — it is the "recompute" answer with a delay knob, wrong-by-a-bound between resets; kept as documented fallback |

Option A's honest weakness: the `users` phase reads `cc_user_minute FINAL` once per run for the
existing-bucket keys (the retraction branch), and the interval expansion covers the whole batch
window even for a one-session straggler. Measured below; at this scale both are sub-second. At
100×, the phase's floor grows with the tier and the window, not with history — and if that floor
ever matters, the recorded mitigations are a key-only projection for the existing-bucket read and
per-day scoping. That is a cost statement, not a convergence caveat.

## What the harness now proves (and could not see before)

`tools/publish-test.sh` previously applied neither `sql/45` nor `sql/50` to its scratch databases —
the defect was structurally invisible to it. Now both databases instantiate both tiers, the control
rebuild rebuilds them the way `tools/build-model.sh` does, and every `compare` covers all four
serving tiers (16 checks). Two new phases exercise the retraction shapes that a set union can never
absorb:

- **PHASE 6 — SHRINK.** A late `pause` lands inside a published interval's 60 s tail grace, with a
  heartbeat after it keeping the run alive: the re-derived interval ends AT the pause, earlier than
  published, and the viewer must be retracted from the minute the tail no longer reaches. This is
  the same shape that exposed the `ReplacingMergeTree(interval_end)` version-column bug
  (`evidence/truncation.txt`).
- **PHASE 7 — DIMENSION CHANGE.** A burst of late heartbeats under a new platform outvotes the old
  dominant value (ADR 0008/0009), so the re-derived interval moves to a different dimension tuple:
  every minute it covers must leave the old platform's user buckets and hour curves and enter the
  new one's.

## What this cost, measured

All from `evidence/publish.txt`, Cloud 26.2.1.525, scratch databases `sonyliv_pub` /
`sonyliv_pub_ctl`; 905,558 events plus 1 injected straggler, 2 shrink events and 9 flip events.

| Stage | Sessions | hours phase | users phase | Convergence (all 4 tiers) |
|---|---|---|---|---|
| bootstrap via the finalizer | 6,659 | 14,558 rows · 1,212 ms | 49,474 buckets · 1,812 ms | 0 differing |
| 5 open sessions catch up | 5 | 10,202 rows · 708 ms | 29,290 buckets · 623 ms | 0 differing |
| whole remaining stream | 7,718 | 23,654 rows · 696 ms | 83,658 buckets · 695 ms | 0 differing |
| one straggler, 46 min behind | 1 | 21,878 rows · 599 ms | 43,015 buckets · 661 ms | 0 differing |
| SHRINK (late pause in the tail) | 1 | 21,878 rows · 1,394 ms | 40,233 buckets · 637 ms | 0 differing |
| DIMENSION FLIP (platform outvoted) | 1 | 10,658 rows · 547 ms | 13,443 buckets · 571 ms | 0 differing |
| 200 unchanged, forced | 200 | 24,548 rows · 657 ms | 81,190 buckets · 846 ms | 0 differing |

User peak 2,737 (truncated slice) → 2,844 (full stream) and hour-tier peak 2,825 → 2,917, identical
by both routes at every stage. The SHRINK case moved minute `2026-07-26 11:30` from 197 sessions /
191 users to 196 / 190 — the user retraction the set union could never express — and the flipped
interval left `IPHONE` for `FlipOS-ADR0016` on all tiers, with 9 injected events outvoting 8.

Note what the 5-session row says about the design: a 5-session batch re-derived 10,202 hour-cube
rows and 29,290 user buckets, because the scope is a TIME window (the batch's sessions spanned
~53 minutes), not a session list. That is the deliberate trade from the decision: full-bucket
recompute is what makes replacement — and therefore retraction — correct, and its cost is bounded
by the window. Both phases stayed around 0.5–1.8 s at every stage, against ~3.5–5 s for the four
pre-existing phases of the same runs.

## Consequences

- **`make reconcile` is untouched and stayed green**: 17,028 minutes, 0 mismatched, peak 2,917.
  Nothing here writes `sonyliv`; the graded database still carries the pre-ADR-0016 shapes until an
  operator runs `make model` (which now migrates `cc_user_minute` by DROP + re-apply — it is pure
  derived state) or applies the publisher.
- **Retraction leaves tombstones.** Empty user-states and all-zero hour rows accumulate keys until
  the next full rebuild. Storage, not correctness: the views filter them, and FINAL keeps one row
  per key. A rebuild's TRUNCATE clears them.
- **The serving views changed contract slightly**: `v_user_concurrency_minute*` now read FINAL
  (mandatory under the new engine) and drop zero-user rows; `v_concurrency_hour*/day*` drop
  all-zero rows. The zero-row filter deliberately does NOT hide negative values — peak and integral
  stay signed so a broken delta model still shows up loud.
- **`tools/build-model.sh` populates the user tier explicitly** (stage 2/6) instead of relying on
  an MV side effect during the intervals insert, and refuses nothing: a pre-ADR-0016 engine is
  migrated by DROP + re-apply with a loud message.
- **Crash/concurrency invariants are inherited, not fixed.** The consumed-before-claimed window,
  the single-publisher assumption and the `marked_at` identity (audit §4.3–4.5, queue Q8–Q10)
  remain open; this ADR adds only idempotent, replay-safe statements to the existing phase chain,
  so it neither widens nor narrows those windows.
- **`sql/45_user_concurrency.sql` is no longer a pure "apply once" file** — applying it runs a full
  bucket re-derivation (idempotent, seconds at this scale). That is intentional: it makes the file
  the single canonical derivation for both the rebuild and the publisher to template.

## What was rejected, and why it is recorded

- The signed per-user representation (option B): 1.52× the rows before any correction lands, an
  unbounded append-only tombstone stream after, and a two-level aggregation on every dashboard
  read. Rejected on the read-path cost — the tier exists to make user concurrency a cheap read.
- The periodic reset (option C): correct only at reset instants, O(history) per reset. It survives
  as the FALLBACK if the replaceable tier is ever found wanting: `TRUNCATE cc_user_minute` + the
  canonical INSERT, 1.8 s at this scale, and the publisher's phases are no-ops on
  top of it (idempotent by construction).
- Keeping the MV alongside the new engine: rejected outright — under replace semantics a per-block
  partial state is not merely wasteful, it is corrupting (it can ERASE a complete bucket), which is
  why retiring it is part of the decision, not housekeeping.
