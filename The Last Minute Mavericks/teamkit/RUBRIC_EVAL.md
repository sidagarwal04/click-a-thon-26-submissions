# Top-10 Rubric Evaluation + Gap-Fill Plan

Evaluated against the judges' "How to get to the Top 10" tracks **and** the internal
`REVIEW_ACTION_PLAN.md` (unseen-readiness audit). Every number below is **measured**, not claimed
— re-run with `tests/detection_eval.py` and `run_incident.py`.

---

## Scorecard (honest)

| Rubric track | Where we are | Score | Biggest lever |
|---|---|---|---|
| **01 · Ship something real** | Live engine + API + UI on real 9M-row data, public on the internet, recomputes live, Langfuse-traced. Not a mockup. | **8.5/10** ✅ | Keep it; it's our strength |
| **02 · Speed as the story** | We HAVE the speed (below) but don't SHOW it — no benchmark in the demo/UI | **5/10** ⚠️ | **Easiest points on the board** — package the before/after |
| **03 · Build for adoption** | Customer/impact/scale are real but implicit, not stated | **6/10** ⚠️ | One crisp customer+$+scale statement |
| **Goal · impossible to ignore** | A metric move becomes a named, evidence-backed, self-explaining diagnosis + audit trace | good | Ride tracks 01–03 |
| **Cross-cutting · does it actually work on unseen?** | Perfect on the 4 seen (34–51% moves); **degrades on overlapping/concurrent anomalies** | **~0.60 recall** ⚠️ | **The one real correctness risk — fix localization** |

---

## Track 02 — the speed story (measured, ready to use)

| What | Measured |
|---|---|
| Cube drill-down (fill_rate × os_version, 3-day window) | **45 ms** |
| Same drill-down on the raw 9M-row fact table + JOIN | 64 ms |
| **Full RCA sweep — 1,709 segments × 3 metrics = 13,672 checks** | **9.9 seconds → 4 incidents + 6 ruled out** |
| Same work done manually (dashboard-slice at ~30s each) | **≈ 114 analyst-hours** |

**The hero line:** *"114 analyst-hours of dashboard-slicing → 10 seconds. On a database where the
same sweep at petabyte scale is still seconds."* This is measured and unused. **Surface it in the UI
eyebrow + demo.** (rubric 02, review P-none — pure packaging)

---

## The one real correctness risk — localization, not sensitivity

The review flagged `precision=recall=0.57` (seed 7) as "detector tuned to seen data." I reproduced it
across seeds and found the **actual** failure mode — it's more specific and more fixable than the
review assumed:

| seed | precision | recall | what it missed |
|---|---|---|---|
| 1 | 0.80 | 0.67 | overlapping fill_rate anomalies in one window → 1 global FP |
| 2 | 0.67 | 0.67 | finance + NAM same window → 2 global FPs |
| 7 | 0.57 | 0.57 | banner + iOS 17.2 localizable, called global |
| 11 | 0.44 | 0.50 | 5 global FPs, each in a missed-localized window |

**Across every seed, nearly every false positive is a `GLOBAL_UNLOCALIZED` verdict in the *exact
same window* as a missed localized incident.** The detector **sees the movement but over-declares
"global"** when ≥2 localized anomalies overlap (many segments move → looks broad → uniformity gate
says global). It is **not** failing to detect; it is failing to *localize*. The same fix lifts BOTH
precision and recall (each same-window FP+miss pair becomes one TP).

Why it matters for judging: on the **seen** 4 (isolated, 34–51%) we are perfect. The **unseen** slice
may contain *concurrent* anomalies — exactly the case we currently mislabel.

---

## Prioritized plan to fill the gaps

Ordered by (points gained × ease). P0 is the only one touching correctness.

### P0 — Fix global-vs-local localization *(core correctness; ~half a day)*
Root cause is measured (above). Two changes in `run_incident.py`:
1. **Localize before declaring global.** Before `GLOBAL_UNLOCALIZED`, run contribution/purity descent
   and check whether a *small set* of segments explains most of the delta. Declare global only when
   **no small segment set explains ≥ ~25%** of the movement (review P1.5). Allow a **multi-segment**
   localized verdict (two concurrent culprits) instead of collapsing to global.
2. **Contamination exclusion** (review P1.1): exclude already-detected incident windows from other
   incidents' baselines — this is why an adjacent injection was killing INC-B/INC-C in the eval.

Acceptance: seeds 1/2/7/11 precision **and** recall → ~0.8+; the 4 known incidents survive under
contamination; global verdict only fires for genuinely global moves (INC-A).

### P1 — Make multi-seed eval the scoreboard *(proves robustness; ~1–2 h)* — review P9
`tests/detection_eval.py` is now recovered. Add `--seeds 1-20`, aggregate precision/recall p10/mean,
break down by metric and by localization type (global/1-D/2-D), include spikes not just drops. This is
the number we *show judges* to claim robustness. Gate: fail if p10 recall < 0.8.

### P2 — Package speed as the hero *(rubric 02; ~1 h, pure win)*
Put the measured before/after in the UI eyebrow + demo: "13,672 checks · 9.9s · vs ≈114 analyst-hours",
plus the 45 ms drill-down latency badge on each evidence chip. Already have the numbers.

### P3 — State the adoption case *(rubric 03; ~30 min)*
One paragraph, slide-ready: **Customer** = InMobi yield / ad-ops. **Use case** = automated RCA on
revenue / fill-rate / eCPM drops that today take an analyst hours of manual slicing. **Impact** =
analyst-hours saved + revenue protected (catch a fill-rate collapse in minutes, not the next morning).
**Scale path** = already a deployed service (mercury API), ClickHouse scales the same sweep to
petabytes, Langfuse gives audit/compliance. Put in `VISION.md` + `DEMO.md`.

### P4 — Revenue as a first-class scanned metric *(rubric 01/02 narrative; ~2 h)* — review P2
Add `revenue` to `SCAN_METRICS` so a headline can open *"Revenue fell 18%"* then decompose into
requests / fill / eCPM (the funnel identity we already compute). Matches the PS framing ("key metrics
moving") better than opening on a driver.

### P5 — Depth polish *(lower priority; substance already exists)*
Review P4 (more analysis in named SQL templates + query_id/rows/bytes per stage), P6 (evidence-register
*every* number incl. baselines/deltas, not just observed values), P7 (deeper Langfuse spans per gate
with pursue/prune reasons). These raise the "ClickHouse depth" and "trace completeness" scores; none
is a correctness risk.

---

## What's ALREADY closed since the review was written
The review predates the deploy/UI work — these are done: **P5** (bundle contract drift — UI no longer
crashes on engine JSON; `_normalize_api()` bridges it), **P10** (UI shows real engine output, live from
the API, not a static answer key), **P8** (requirements.txt complete, `.venv` standard). See `GAPS.md`.

## Bottom line
Track 01 is won. Tracks 02 and 03 are **packaging**, not building — a few hours of surfacing numbers we
already have. The single thing that could actually cost us on the unseen dataset is **localization on
concurrent anomalies (P0)** — and it's a specific, measured, half-day fix, not a vague "make detection
better." Do P0 + P1 + P2 before anything else.
