# Design rationale — answering the scope and overengineering audit

An audit of this repo against `PROBLEM_STATEMENT.md` raised six findings: that the React UI,
the containerised multi-worker API, the rollup layer and LangGraph are out of scope or
overengineered; that the false-positive rate is a trustworthiness risk; and that the
hallucination guardrails are sound.

This document answers each one. Where the objection is right it says so and shows the number
that makes it right. Where it is wrong it does not argue — it measures. Two of the six
findings survived contact with the evidence and produced code changes; one was partly
conceded; three did not survive.

Each section states the charge as written, then answers it.

---

## 1. "A React UI is an explicit violation — polished frontends are out of scope"

**Not sustained.** The two sentences are in the same document and are not in conflict:

> **Out of scope.** Authentication, production deployment, alerting integrations (PagerDuty
> and friends), and polished frontends. Judges reward the investigation loop, not the
> scaffolding.

> **Suggested demo.** Replay an incident end to end: a metric drops → the system runs → a
> metric tree lights up green/amber/red → a plain-English diagnosis → optionally, ask a
> follow-up question in chat.

The second paragraph describes a user interface: a colour-coded metric tree and a chat box.
"Polished frontends" is a statement about what earns marks — polish does not — not a
prohibition on the surface the brief itself prescribes. It also names a *conversational
interface* as one of the three integrations that qualify.

The test the UI is actually held to is therefore: **does every screen discharge a judged
criterion, or is it decoration?**

| Screen | Judged criterion it serves |
|---|---|
| `/` — funnel over the revenue identity, work queue ranked by $/day | Detection & localization; "a metric tree lights up green/amber/red" |
| `/incidents/:id` — causal chain, mechanism, proof charts, ruled-out with numbers | Localized; Honest; Explanation trustworthiness |
| `/incidents/:id` — verbatim query trace with scanned-row counts | Traceability; analytical depth in ClickHouse |
| `GET /api/coverage` — what was and was not evaluated, with the number behind each skip (formerly the `/coverage` page; the surface was folded into the API when the UI was slimmed) | Honest — the gaps are stated rather than discovered |
| `GET /api/calibration` — the backtest record, including rejected thresholds and the false-alarm count (formerly the `/method` page) | "avoid crying wolf on noise", stated by the system about itself |
| Chat on every incident | The brief's follow-up question; the conversational-interface integration |

Nothing on screen is there to look finished. The UI is also the only artefact that renders a
trace a judge can *follow* — a Langfuse timeline shows what ran, but not why one segment was
blamed and another cleared.

**What did change.** The audit was right that the UI served analysts and nobody else. Two
additions came out of it: a deterministic **causal chain** (`engine/causal_chain.py`) that
states the diagnosis as one because-ladder in plain English above the charts, and a
**Summary / Full evidence** toggle that collapses the dense sections by default. Neither
removes anything — Summary mode changes what is open, never what exists.

---

## 2. "Engineering a stateless multi-worker API and a background scanner is overengineering"

**Partly sustained, and the framing was wrong.** `PRODUCTION_PLAN.md` opened with
"Production-level and scalable is the top priority", which invited exactly this reading and
is not what the brief rewards. That sentence has been rewritten: the goal is surviving the
**unseen dataset**, which is a correctness requirement the brief states explicitly, not
throughput this system will never see.

What remains, and why, on that narrower justification:

- **Containerised, one command.** `./scripts/deploy.sh` exists so the artefact that runs
  against the unseen incident is the one the tests passed against. Requirements are pinned
  for the same reason (`requirements.txt` documents this).
- **The scanner as its own process** is not a scalability choice; it is a correctness fix.
  The API runs `--workers 2`, and a FastAPI lifespan task runs once *per worker*, so every
  scan tick was silently duplicated — visible as doubled rows in the event feed (gotcha #3).
  Splitting the process is what removed the duplicate, and it would be needed at one request
  per hour.
- **Statelessness** costs nothing here: evidence lives in ClickHouse and Langfuse because it
  has to be re-readable by a judge, not because of replica count.

No claim is made that this system is production-ready, and the docs no longer imply it.

---

## 3. "19 pre-aggregation tables for 9M rows is severe premature optimisation"

**Partly sustained — and this is the section where the measurement disagreed with us, not
with the auditor.** The reasoning offered was that ClickHouse scans 9M rows in milliseconds
anyway. `scripts/bench_rollups.py` runs each real question both ways — against the rollup the
engine uses, and as the equivalent scan of raw `ad_events` with dictionaries joined — and
checks that both return the same numbers before comparing them.

| Question | Rollup | Raw `ad_events` | Speed-up | Rows scanned | Same answer |
|---|---|---|---|---|---|
| top-line fill rate, 1d | 47 ms · 720 rows | 47 ms · 319,488 rows | **1.0×** | 444× fewer | yes |
| fill rate by region (ranking) | 32 ms · 3,600 rows | 47 ms · 319,488 rows | **1.5×** | 89× fewer | yes |
| fill rate by app (highest cardinality) | 47 ms · 57,344 rows | 47 ms · 319,488 rows | **1.0×** | 6× fewer | yes |
| fill rate by geo cell (the composite scope that found the planted incident) | 47 ms · 8,192 rows | 62 ms · 319,488 rows | **1.3×** | 39× fewer | yes |
| 35-day daily revenue series | 47 ms · 840 rows | 94 ms · 9,000,000 rows | **2.0×** | 10,714× fewer | yes |
| 28-day hourly series by region (band building) | 62 ms · 3,600 rows | 219 ms · 7,132,992 rows | **3.5×** | 1,981× fewer | yes |
| 28-day hourly series by app (the most expensive band build) | 78 ms · 991,232 rows | 188 ms · 7,132,992 rows | **2.4×** | 7× fewer | yes |

Median speed-up **1.5×** across seven queries; five bought less than 2×. One is *slower* in
the noise.

**So the auditor's premise is correct: at this data size, a single rollup query is not
meaningfully faster than scanning the fact table.** Per-query overhead dominates and 9M rows
really is small. Any defence of the rollups that rests on "otherwise it would be slow" is
refuted by this table, and we are not going to make it.

The defence that survives is different, and narrower:

1. **Scanned volume, not latency, is what scales.** The ratio the rollups actually change is
   6× to 10,714× fewer rows read. Latency is flat *today* because the fact table is small; the
   scanned-row ratio is the quantity that stays true when the unseen dataset is not.
2. **The unit of work is a sweep, not a query.** One full sweep issues **364 queries** and
   performs **133,775 band evaluations** in 7.6 s. The relevant comparison is not one query
   against one query but that whole sweep against 364 fact-table scans — and the heaviest
   stage, band building, is the 28-day shape where the ratio is ~2,000×.
3. **ClickHouse Cloud meters scanned data.** A 1.0× latency win that reads 444× less is still
   a win in the dimension that is billed.

That is a weaker claim than the one the plan originally made, and it is the one the numbers
support. Reproduce with `python scripts/bench_rollups.py --markdown`.

---

## 4. "LangGraph is bloat around what is really a deterministic while-loop"

**Not sustained on the facts, though the instinct is reasonable.** `engine/graph.py:89`,
`should_keep_drilling`, is a genuine conditional cycle: `drilldown` routes back into
`drilldown` and terminates on three separate conditions — nothing left to drill, the top
segment's `share_of_total_delta` falling below `settings.drilldown_concentration_threshold`,
or `settings.max_drilldown_depth`. It replaced a hardcoded two-level special case; the
recursion depth is data-dependent and differs between incidents.

Two things follow that a hand-rolled loop would not give:

- The compiled topology is itself a **traceability artefact**. `get_graph().get_graph()`
  emits the node/edge structure, so what was checked and in what order is inspectable
  statically, not only by reading a transcript.
- The state machine is the thing that keeps the LLM out of the loop. Every node is a
  deterministic Python + SQL call, and `narrate` is the single LLM-touching node, running
  last, over an already-built `EvidenceBundle`. That constraint is visible in the graph
  definition rather than being a convention someone has to maintain.

The honest counterpoint: this is a small graph, and a `while` loop with the same three exit
conditions would behave identically. LangGraph is not load-bearing for correctness. It is
kept because it costs one dependency and makes the control flow declarative and inspectable,
which is what the traceability criterion rewards — not because a loop would not have worked.

---

## 5. "k = 3.0 still yields 109 false positives; the statistical approach is flawed"

**Sustained. This was the one finding with teeth, and it produced the substantive change in
this pass.** It sits directly under a judged line — *"did you avoid crying wolf on noise?"* —
and it was previously defended in prose rather than reduced.

It was also worse than the audit knew. The 109 figure is already **post-gate**:
`scripts/backtest.py:76` counts `alertable()` output, which filters on `gated_by_impact`. So
the $1.00/day dollar gate was not what was failing to hold these back.

The cause is arithmetic, and the old `PROGRESS.md` named it while excusing it — "z-scores on
very low-variance ratio metrics (like fill_rate) can run high in magnitude even for small
absolute moves ... not a bug." It is a bug. A slice whose trailing history happens to be
nearly flat has a MAD near zero, and dividing by a near-zero spread turns a fraction of a
percentage point into a six-sigma verdict. A slice like that can still be worth more than the
gate, so nothing downstream catches it.

Two floors now apply, both in one place (`engine/bands.py:evaluate()`), both relative to the
band centre so they carry to a dataset on different scales, and both defaulting to `0.0` so
the unfloored arithmetic is exactly reproducible:

- **`min_relative_spread`** — a band may not be narrower than this fraction of its own
  centre. Fixes the divide-by-near-zero directly.
- **`min_relative_move`** — a breach must also be large in absolute terms. This is a second,
  independent argument rather than a stricter version of the first: the difference between
  *improbable* and *material*, and a finding has to win both. A breach that clears sigma but
  not the effect floor is recorded as `suppressed` with the number that suppressed it — not
  skipped, not dropped, the same contract as the dollar gate.

### The measurement

All 35 days replayed, floor ∈ {0, 2%, 5%}. **Every setting detected both planted incidents on
the same days** — Jun 24 and Jun 29, the earliest sweep that could see each — so the detection
gate eliminated nothing and the choice came down to cost:

| Spread floor | Raises on quiet days | Distinct slices | Quiet days with a raise | Median breaches/day | Smallest detectable move |
|---|---|---|---|---|---|
| none (before) | 109 | 98 | **21 of 29** | 290 | — |
| **2% (adopted)** | **88** | **83** | **16 of 29** | 146 | **6%** |
| 5% | 74 | 70 | 8 of 29 | 60 | 15% |

At the adopted setting: **−19% raises, −15% distinct slices, and quiet days with an alarm fall
from 21 of 29 to 16 of 29 — at zero detection cost.**

### Why 2% and not 5%, when 5% raises fewer

Because the false-alarm column cannot see what the higher floor costs. A spread floor works by
widening the band, so `k × floor` is the smallest relative move that can **ever** breach — at
k = 3, a 5% floor means nothing moving less than 15% is detectable on any scope at any grain.
Both planted incidents are ~20%+ moves, so this replay prices that difference at exactly zero,
and a table that cannot price a cost will always recommend paying it.

2% cuts false alarms by roughly a third of the way to 5%'s figure for a 6% detection threshold
that is defensible as a materiality bar; 5% buys the remainder by going partly blind. This is
the same reasoning that stopped `band_k_amber` being tightened past the evidence, applied
consistently. The scorecard now carries a **smallest detectable move** column so the trade is
visible in the table rather than argued in prose, and `scripts/backtest.py --adopt` makes the
adopted row a declaration with its reason attached, rather than an automatic
fewest-false-alarms pick.

### What the effect floor turned out to be worth: nothing, here

`min_relative_move` was measured and **found redundant**. With the spread floor present it
changed no figure at all (88/83 with and without at 2%; 74/70 at 5%), and alone it moved 109
raises to 108. It ships defaulted to `0.0`. The capability is retained because the two are not
the same test and a dataset whose spread and effect diverge would need it — but enabling a
knob whose measured contribution here is nil would be exactly the overengineering this audit
was about.

### Two false-alarm measures, because neither is honest alone

Raw day-raises over-count a single mis-baselined slice that re-fires daily; distinct root
fingerprints under-count a genuinely noisy day. Both are always reported.

### What has not changed

The replay contains no weak or slow incident, so it says nothing about the sensitivity these
floors cost. That limit is stated in the calibration record (`GET /api/calibration`, backed by
`Docs/BACKTEST_SCORECARD.md`) rather than left for a judge to find.

---

## 6. "Hallucination guardrails are correctly implemented"

**Agreed, and unchanged in substance** — see the Guardrails section of `CLAUDE.md`. The LLM
restates numbers already computed; it never queries, never calculates; narration failure
degrades to an explicit "narration unavailable" rather than a templated guess.

One gap was found while auditing the auditor, in the surface the audit did not examine.
`engine/narrator.py` was wrapped in a Langfuse generation span; `engine/chat.py` called the
provider bare. The **one interactive LLM surface produced no trace at all** — the worst
possible one to miss under "no trace, no credit", since a judge typing a follow-up is exactly
when traceability is being tested. Chat turns now open their own root span
(`tracing.traced_chat`), because a follow-up arrives on a later HTTP request when no
investigation span is live.

The chat prompt was also not held to the rule the narrator follows: it asked for "the
specific dimension/value/number" but not for the `source_step`. Every other narrated claim in
the system points at a runnable query; chat answers now do too.

---

## Summary

| # | Charge | Verdict | What changed |
|---|---|---|---|
| 1 | React UI is out of scope | Not sustained | Causal chain + Summary/Full mode, for the non-analyst reader |
| 2 | Production deployment is overengineering | Partly sustained | Docs reframed around the unseen dataset; scaling claims dropped |
| 3 | 19 rollups is premature optimisation | Partly sustained | Benchmarked; the latency defence is withdrawn, the scanned-volume one measured |
| 4 | LangGraph is bloat | Not sustained | Nothing; the recursion is real, and the rationale is now written down |
| 5 | False-positive rate | **Sustained** | Spread floor adopted at 2%, backtested: quiet days with an alarm 21 of 29 → 16 of 29, zero detection cost. Effect floor measured, found redundant, shipped off. `GET /api/calibration` |
| 6 | Hallucination guardrails | Agreed | Chat traced and held to the `source_step` rule |
