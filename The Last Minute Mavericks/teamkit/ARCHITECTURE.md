# Architecture — lean but not naive (InMobi-mentor-aligned)

The north star. An InMobi mentor's feedback: RCA is fundamentally *"slice the moved metric by
dimension, compare to a baseline, name the segment"* — analysts do it across dashboards by hand.
We automate exactly that loop, no more. This doc supersedes the sprawl; `CONTRACTS.md` remains the
interface spec, trimmed per below.

## Principles (the constraints)
1. **Only the given ad-events dataset.** No external data, no correlation/events feed, no signups.
2. **Minimal ClickHouse footprint:** the 4 raw tables + **one cube**. No table sprawl (no history,
   registry, or events tables).
3. **ClickHouse does all analysis (SQL). The LLM only narrates.**
4. **The 4 judging pointers are the acceptance test:** Fast · Trustworthy · Localized · Honest.

## The loop (all SQL over the cube — except step 5)
```
 1. DETECT    metric vs same-weekday baseline → is the move real?          → Fast
 2. SLICE     break the move down by each low-card dimension                → Localized
 3. RANK      contribution per segment; handle dilution + 2-D → name the    → Localized
              RIGHT segment (not an artifact)
 4. RULE OUT  test siblings: request volume, CTR, seasonality → what's clear → Honest
 5. NARRATE   LLM writes prose citing ONLY computed evidence numbers        → Trustworthy
```
ClickHouse does 1–4. The LLM does 5, and a validator blocks any number not backed by a query.

## The entire ClickHouse footprint
| Object | What | Why |
|---|---|---|
| `rca.ad_events` + `apps` + `advertisers` + `geo_device` | given raw data | source |
| **`rca.cube`** | AggregatingMergeTree MV — **sums** by (day × low-card dims) | the *Fast* enabler; **same data, pre-aggregated** — not a new dataset, not over-engineering |
| `rca.incidents` *(optional)* | small results table (last run) for the trace/UI | convenience; can also be query output |

That's it. Everything else is SQL over these.

## Lean but not naive — keep vs trim
The planted anomalies are **booby-trapped for the naive version**: INC-D is a 2-D interaction
(`iOS 18.1 × APAC`, −50.7%); a plain slice-and-rank names the *dilution artifact* `iPhone 14`
(−5.9%) instead. So we keep exactly the logic that names the right segment, and cut the rest.

**KEEP (each maps to a scored pointer / a real trap in the data):**
- Robust **same-weekday baseline** — weekends aren't anomalies; C measured that a flat/too-short
  baseline over-flags. Justified.
- **Contribution ranking + 2-D / dilution ("purity") handling** — the difference between passing
  and failing *Localized* on INC-D.
- **Volume + effect-size gates** — stop crying wolf (the rubric penalizes noise as much as misses;
  measured: naive p-values → ~84 false positives/run).
- **Evidence + `query_id` trust layer** and the **ruled-out ledger** — *Trustworthy* + *Honest*.

**TRIM (research value, not scored — mostly my sprawl + a couple of C's flourishes):**
- ❌ external `events`/correlation table and the layered data model (**my** over-reach) → gone.
- ❌ Shapley-vs-LMDI cross-check + order-sensitivity proofs (CONTRACTS §4) → the decomposition is
  fine without proving it three ways.
- ❌ elaborate verdict state machine → keep **three** outcomes: `localized` / `global` / `inconclusive`.
- ❔ Adtributor's second "surprise" axis → optional; contribution + purity is the core ranker.
  (Keep Adtributor only if cheap + we want the citation for Innovation.)

## OSS integration (unchanged — all four, per STACK_INTEGRATION.md)
ClickHouse (engine) + Langfuse (trace/eval — done) + ClickStack (latency) + LibreChat (deep endpoint).
"ClickHouse three ways." The integrations aren't the over-engineering the mentor flagged — that was
the analytics/data model, now trimmed.

## What this means for the build
1. `sql/` — build the **cube**, then detect → slice → rank(+purity) → rule-out. (A)
2. Plug the detector into `tests/battletest.py` → precision climbs from 0.12; each run traces to
   Langfuse (already wired). (A + B)
3. `agent/` narrate + validator over the evidence; `run_incident.py` chains it. (B)
4. Integrations + one-page UI. (C)

> Net: **simpler than the current contracts, still robust enough to name the right segment on the
> booby-trapped incidents.** Coordinate the §4/§5/§6 trims with C (owner) before deleting.
