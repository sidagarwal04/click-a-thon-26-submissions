# Design bake-off: `feat/problem-space-research` vs the incumbent (ADR 0012/0013/0016)

> **Recommendation: REJECT wholesale adoption — confidence HIGH (~90%).** The branch was written
> 16:20–16:39 today, 3–6 hours **before** ADR 0012 (19:30), ADR 0013 (20:10) and ADR 0016 (22:34)
> landed; as an architecture it is superseded, not wrong. The incumbent passes the graded gate on
> **17,028 minutes / 0 mismatched** with scratch-proven four-tier convergence the challenger lacks.
> **CHERRY-PICK four things as ideas, not code — confidence MEDIUM (~70%):** the source-contract gate
> (run it before the unseen day), the single-writer lease (our open Q9), fresh dedup tokens per
> rebuild, and its independent semantics as dossier evidence — it reads **~11% below us** on watch-time.

**Adjudicated:** 2026-08-01, from `git diff 4a265fc...feat/problem-space-research` (never checked out).
**The nine commits:** `7a27962` (the coupled core, ~4,080 of 4,339 inserted lines) plus eight small,
genuinely separable satellites (`d276b70`…`9b2cac7`).

---

## 1 · What it actually proposes, stripped of advocacy

One sentence: an **event-time, state-gated sessionizer** (independent foreground/background and
play/pause state machines; a heartbeat counts only while *both* are active, fail-closed) whose output
is the same hour-clipped signed-delta ledger we use, plus a **published-run correction overlay** for
late data (`target − base` replacement deltas, phase-logged `prepared→staged→published`), plus a
**version-fenced exact-tail snapshot** for the last 900 s, plus an operator lock.

It is **not one design — it is one coupled core plus ~10 separable ideas.** The core (sessionizer +
correction finalizer + tail) is a parallel implementation of the same problem the incumbent solves.
The separable satellites: a 76-line source-contract acceptance gate, an `mkdir`-based single-writer
lock + an ADR demanding an external lease, a model-version SQL fingerprint, bitemporal `--as-of-run`
replay, "filtered peak is not additive" doctrine (ADR 0015, docs-only), a data-audit SQL file,
query-range validation, a summary-vs-curve equivalence check, and fresh `insert_deduplication_token`
per rebuild.

**Context that explains everything:** it forked from `4a265fc` (14:10), when `sql/` held only
`00_schema`, `05_users.sh` and `10_intervals.sql`. It evolved **`sql/10_intervals.sql` — the legacy
builder that dev has since replaced with `sql/30_build_intervals.sql`** — and it numbered its ADRs
0007–0015, **all nine of which collide** with different decisions now on dev (dev is at 0018).

## 2 · Overlap vs genuine difference

| Axis | Challenger | Incumbent (dev) | Verdict |
|---|---|---|---|
| Delta ledger, hour-clipped, ±1 at minute boundaries | yes | yes | **Overlap** (both grew from ADR 0003) |
| Correction = re-derive dirty sessions, replace-by-diff, zero tombstones | `target − base` staged overlay | `−old + new` appended (ADR 0006/0013) | **Overlap** — same mathematics, different plumbing |
| Run log with phases as the crash story | 4-phase enum, `max(phase)` visibility | 8-phase `cc_publish_runs` + dedup tokens | **Overlap** |
| Single-writer requirement | **implemented** (lock) + ADR demanding external lease | **admitted open gap** (queue Q9, ADR 0019 reserved) | Challenger is ahead here |
| Sessionizer semantics | state-gated, fail-closed after unmatched background; `VideoError` non-terminal; half-open minute boundary; tie-break stop→start→heartbeat; payload dedupe in derivation | gap+pause lease (GAP_S 150 / TAIL_S 60), inclusive minute boundary (doubts/05), same-second resume (ADR 0009), dedupe **not** validated at dimension grain (doubts/06) | **Genuine difference** — different numbers on the same data |
| Result on the corpus | 30,931 intervals / **1,762.4 h** | 30,323 intervals / **1,978.1 h**, peak 2,917 | Challenger counts **10.9% less** watch-time |
| User-distinct tier, hour/day cube | none — doctrine says sessions-only; ADR 0015 forbids precomputed per-dimension max | `cc_user_minute` + `cc_hour_agg`, publisher-owned (ADR 0016), convergence-tested | Incumbent only |
| Freshness of newest minutes | bounded exact-tail snapshot + fence | continuous publisher, ~68 s floor, handles open sessions (proven PHASE 3) | Both solve it; incumbent's is proven, tail becomes redundant |
| Session-independent baseline (`cc_minute_stateless`, the mandated 2,894-vs-2,917 comparison) | **deleted**, replaced by prose | live, queryable | Adopting wholesale **removes a deliverable** |

Neither reconcile gate can adjudicate the semantic differences: each design's gate re-derives truth
using **its own conventions**, so both are green on their own terms. The 10.9% gap is a
ground-truth question (the doubts/02–06 axis), not something either gate can settle.

## 3 · What it does better (the steelman)

- **It closes, today, the P0 gap our own audit filed as Q9**: a real writer lock plus an honest ADR
  that a local lock is not a distributed lease. The incumbent's concurrent-publisher hazard
  (`2X′ − X` corruption) is documented but unfixed.
- **A source-contract acceptance gate** (9 hard-failure probes + `throwIf`, standalone) — exactly the
  fail-closed front door the unseen day needs. The incumbent has nothing equivalent.
- **It caught a real rebuild-repeatability trap**: block-dedup metadata surviving `TRUNCATE` can
  silently swallow re-inserts; its fix is a fresh `insert_deduplication_token` per rebuild.
- **Its semantics are a defensible reading of the problem** — arguably *more* literal on
  "excluding backgrounded and paused periods" (hard state gates, fail-closed) than the incumbent's
  lease model. Its half-open minute boundary is precisely the alternative doubts/05 says our gate
  cannot see. As an independently-built second implementation, it bounds our semantic risk for free.
- ADR 0015 ("a precomputed peak is valid only for its exact filter cuboid") is mathematically right
  and worth a one-time check against our required-shape results (b09, the partial-platform cut).

## 4 · What it costs

- **Total architectural rework.** It edits the superseded `sql/10_intervals.sql`; dev builds from
  `30_build_intervals.sql`. Its table set, tools and nine colliding ADR numbers would displace the
  publisher (ADR 0013/0016), the 16-check convergence proof, the 13-query benchmark bundle, the
  dashboards and the demo harness — the entire evening's verified work.
- **Verification asymmetry is stark.** Incumbent: 17,028 minutes / 0 mismatched on the graded DB;
  seven-phase scratch convergence with straggler/shrink/flip cases. Challenger: a 5-minute sampled
  reconcile **on a local Docker container**, no committed `evidence/reconcile.txt`, an **empty**
  `evidence/mv_cost.txt`, and Cloud never reached (its `.env` still holds the template host).
- **A graded-DB foot-gun on the day we corrupted it once already**: its README documents
  `TARGET=cloud tools/materialize.sh --replace`, which truncates 7 tables in whatever `CH_DATABASE`
  names — `sonyliv` in `.env.example`.
- Nine commits of effort is sunk cost, not an argument; and its lower watch-time number is a
  hypothesis, not evidence — nothing shows judge spot-checks prefer it.

## 5 · Recommendation

**Reject the architecture; strip it for parts. Do not merge, rebase, or renumber the branch.**

1. **Reject wholesale adoption** — HIGH (~90%). Superseded by ADR 0012/0013/0016, which landed
   3–6 hours after it was written. That is timing, not a criticism of the branch.
2. **Cherry-pick as re-implementations against dev's layout** (new commits citing the branch; the
   files themselves target the old world) — MEDIUM (~70%):
   a. `queries/validate_source_contract.sql` + runner → run before loading the unseen day.
   b. `tools/finalizer-lock.sh` + its ADR 0014's lease doctrine → seed of our Q9 fix (ADR 0019).
   c. The fresh-dedup-token-per-rebuild fix (`75b516b`) → audit `tools/build-model.sh` for the
      same trap on Cloud (Shared/replicated engines, where tokens are live).
3. **File its semantic deltas into the dossiers, not the pipeline**: the 1,762.4 h state-gated
   reading → doubts/02; its half-open boundary → doubts/05; its payload dedupe-in-derivation →
   doubts/06. Two independent implementations disagreeing by 10.9% is the strongest exhibit a
   mentor question can carry.
4. Keep the branch unmerged and intact as the reference implementation of the alternative semantics.

## 6 · What would change this recommendation

- **A mentor answer on doubts/02/05 favouring state-gated or half-open semantics** → port the
  *rules* (the eligibility filter, the boundary rule) into `30_build_intervals.sql` as a semantics
  change with a re-run gate — still not a branch merge. This is the likeliest reversal, and it is
  cheap: the gate is one `WHERE` clause.
- **A full-grain reconcile of the challenger on Cloud** (17,028 minutes, not 5 samples) that the
  incumbent could not match — no such run exists today.
- **Evidence the incumbent sums per-cuboid maxes anywhere** (an ADR 0015 violation) in the b01–b13
  answers → the challenger's doctrine and its serving-path design gain real weight.
- **Judges checking distinct users where we serve sessions** (or vice versa) — the two designs
  made opposite metric bets; the incumbent hedges by carrying both tiers, the challenger does not.
