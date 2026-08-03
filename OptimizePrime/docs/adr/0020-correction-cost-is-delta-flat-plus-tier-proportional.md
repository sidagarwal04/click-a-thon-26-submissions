# ADR 0020 — Correction cost is delta-flat PLUS tier-proportional; the publisher binds first at scale

> **Summary:** Re-measuring the scale ladder on the ADR 0016 model (evidence/scale.txt,
> 2026-08-01T17:27Z) shows the six-phase publisher's `hours`+`users` phases grow from 43% of a
> one-straggler correction at 1× to **97% at 100×** (7.5 s total, `hours` peaking at 2.45 GiB —
> it meets a 5.4 GiB box's ceiling between 100× and 200×). The public "1 session in 3.4 s" claim
> is retired: post-0016 the same correction is 5,215 ms on Cloud at 1× and audience-proportional.
> The claim that survives: the four delta phases stay flat (~230–330 ms at every scale). Status:
> accepted, 2026-08-01. Nothing applied to `sonyliv`; batch-path breaks-first is still intervals.

**Status** Accepted · 2026-08-01 · consequence of [ADR 0016](0016-publisher-owns-the-user-and-hour-tiers.md);
re-measures the evidence behind [ADR 0006](0006-late-arrival-correction-by-diff.md)'s cost claim;
supersedes the "3.4 s" figure quoted in `docs/ARCHITECTURE.md`

## Context

`evidence/scale.txt` was produced before ADR 0016, against a model with three build stages and
**no user tier at all** — its scratch databases never instantiated `cc_user_minute`, and its
publish-cost claim ("one session in 3.4 s") was measured when the publisher had four phases.
ADR 0016 changed the engine under those numbers (`cc_user_minute` →
`ReplacingMergeTree(computed_at)`, MV retired, retraction-as-rows) and added two publisher phases
(`hours`, `users`) that re-derive touched buckets **in full** — all sessions covering them, not
just the batch's — because full-bucket recompute is what makes replacement, and therefore
retraction, correct. The ladder was re-run at 1×/10×/100× on the current model, all four tiers
built and reconciled (minute AND user tier: 0 mismatched minutes at every scale).

## What the re-measure found

| Figure | 1× | 10× | 100× | Reading |
|---|---|---|---|---|
| publish total (1 straggler, 6 phases) | 584 ms | 1,248 ms | 7,497 ms | grows ~N⁰·⁶ |
| … of which `hours`+`users` | 252 ms (43%) | 1,012 ms (81%) | 7,251 ms (**97%**) | the correction IS tier maintenance now |
| … the four delta phases | 332 ms | 236 ms | 246 ms | **flat — ADR 0006's claim survives here** |
| `hours` phase peak memory | 41 MiB | 267 MiB | **2.45 GiB** | linear ⇒ hits a 5.4 GiB box between 100× and 200× |
| `users` phase rows read | 145 K | 1.24 M | 9.72 M | audience × window, as ADR 0016 priced |
| user-tier rows appended by ONE publish | +61 K | +459 K | **+1.14 M** (16% of tier) | retraction-as-rows: churn until merges collapse |
| Q8 user-peak serving read | 8.5 ms / 17.8 MiB | 79.7 ms / 194 MiB | **884 ms / 1.50 GiB** | the only serving query that grows with the tier |

Unmoved, and worth saying: deltas and houragg build times/memory are **identical** to the
pre-0016 run, serving queries Q1–Q7 are within noise (bytes read at 100× fell ~3%), the ADR 0008
delta ceiling still holds at 88.8%, and parts/dictionary/stateless-tier candidates did not move.
The engine change was free everywhere except where it deliberately spends: correction.

Separately, the re-measure caught a **non-0016** regression: `sql/30_build_intervals.sql` (ADR
0009's per-event attribution tuple) took the intervals stage from 1.47 → 3.79 GiB at 10×, made
plain spill insufficient at 100× (now needs `max_threads=2` as well), and flipped its time fit
from k=0.98 to k=1.16. The batch path's breaks-first is still intervals — but worse than the
published numbers say. That belongs to ADR 0009's owners; it is recorded here because this run
is the measurement that exposed it.

## Decision

1. **The public cost claim is restated in two parts.** Retire "straggler correction: 1 session
   in 3.4 s" everywhere it is quoted. The defensible sentence is: *"delta correction is
   window-bounded and flat — ~0.3 s at every scale measured; tier maintenance (hour cube +
   user buckets) rides along in the same run and scales with audience × window: 0.25 s at 1×,
   7.3 s at 100× on the test box, 1.3 s at 1× on Cloud."* A flat number for a cost that is
   measurably audience-proportional would be exactly the kind of claim this repo exists not to
   make.
2. **The publisher is named the first thing to break at scale on the incremental path**, and its
   ceiling is a memory number, not a latency number: the `hours` phase at 2.45 GiB/100× on a
   5.4 GiB box. The escalation path, in order, is the one ADR 0016 recorded: (a) key-only
   projection for the `users` phase's existing-bucket read, (b) per-day scoping of both phases,
   and now (c) — new from this measurement — cap `max_threads` on the two phase INSERTs the same
   way the intervals rescue tier does, since both are GROUP BYs whose per-thread hash tables
   multiply peak memory.
3. **The design is kept.** 97% of the correction being tier maintenance is the accepted price of
   having retraction at all (ADR 0016 options table); the alternative representations pay at
   read time forever. The four serving tiers converged with the rebuild at every scale and the
   user gate passed at 100× — the cost bought correctness.

## Consequences

- `docs/ARCHITECTURE.md` quotes 3.4 s twice; `docs/EXPLAINER.md` quotes the old memory-sweep pair
  (t=2 at 2.59 GiB / 50.5 s — now 3.52 GiB / 215.6 s). Both need the restated numbers; those
  files belong to other owners this session, so this ADR is the notice, `evidence/scale.txt`
  the proof.
- Q8-style whole-tier user reads (884 ms / 1.5 GiB at 100×) are fine for a dashboard tile but
  not for a per-request path; anything latency-sensitive should read a filtered dim slice, which
  prunes on the `(platform, country, content_id, minute)` key.
- Sustained publishing churns `cc_user_minute` by the touched window per run (16% of the tier per
  publish at 100×). Merges absorb it; a scheduled rebuild's TRUNCATE remains the tombstone/version
  floor-sweep, exactly as ADR 0016 stated.
- `tools/scale-test.sh` now builds and reconciles all four tiers and times the six-phase publish
  at every scale, so the next engine change under these numbers re-prices automatically.
