# Slide Deck Template — Automated Root-Cause Analyst

> **Goal:** Judges should walk away knowing *what we built, why it's trustworthy, and that it works on data it has never seen.*

---

## Slide 1 — Title

**Content:**
- Team name / members
- "From Alert to Answer: The Automated Root-Cause Analyst"
- One-liner: *"A metric moves. In seconds, the system names the segment, cites the numbers, and shows its work."*

**Visual:** Hero screenshot of the RCA UI showing a completed diagnosis.

---

## Slide 2 — The Problem (30 sec)

**Content:**
- A metric drops → analyst opens 6 dashboards → 2 hours later: "it was Android 15 in EU"
- The data existed from minute one. The bottleneck is the **manual investigation**, not the data.
- **Our goal:** automate the "why" — in seconds, not hours.

**Visual:** Before/after comparison — "Manual: hours, 6 tools, human fatigue" vs "Automated: seconds, one trace, every claim backed by a number"

**What to say:** Keep this relatable. Don't over-explain InMobi's business; the judges have the problem statement.

---

## Slide 3 — Architecture Overview (60 sec)

**Content:**
- **5 layers:** Data → Semantic Layer → Detection → RCA Agent → Narration
- **Core principle:** ClickHouse computes, the LLM narrates. The model never sees a raw row, never does arithmetic.
- Highlight the three key tables: `ad_events_enriched`, `metric_def`, `metric_dim_map`

**Visual:** The architecture mermaid diagram from `architecture.md` — rendered cleanly. Simplify if needed: show the 5-layer flow left-to-right.

**What to say:**
- "Everything is registry-driven. Add a new metric by inserting a row — no code change."
- "One materialized view, two definition tables. No pre-aggregated rollup, no incident table."

---

## Slide 4 — The Investigation Ladder (60 sec)

**Content — the 5 steps:**

| Step | What it does | Why it matters |
|---|---|---|
| 1. Reproduce | Recompute the global series live | Nothing from the alert is trusted as proof |
| 2. Decompose | Log-share allocation over the revenue identity | Tells you *which funnel stage* moved (supply? price?) before asking *which segment* |
| 3. Scan dimensions | Score all 62 slices in ONE query (ARRAY JOIN) | Ranks by contribution, not % change — noisy small segments can't outrank real moves |
| 4. Holdout | Recompute on the complement | Kills bleed-through: Galaxy A54 lights up alongside Android 15, but only Android 15 survives |
| 5. Dependency walk | Cross the leading cut with entangled dimensions | Confirms "every Android 15 device is depressed" → fault is at OS level |

**Visual:** The RCA tree diagram (metric → factors → dimensions → dependencies), plus the sequence diagram showing the step-by-step flow.

**What to say:**
- "No model picks the next step. It's a fixed ladder of parameterised queries."
- "The holdout is the kill shot for bleed-through — the single most important step."

---

## Slide 5 — ClickHouse Does the Work (45 sec)

**Content:**
- Show the semantic layer: `metric_def` table (sql, dependencies, z_score_threshold, guard rails)
- Show `metric_dim_map`: priority-ordered drill paths, dependency edges
- Every formula, threshold, dimension list — in ClickHouse, not in Python
- Baseline: same hour-of-day, same day-type (weekday/weekend), IQR-robust, 20 matching observations

**Visual:** A screenshot or table dump of `metric_def` showing 2–3 rows.

**What to say:**
- "The judge can open `metric_def` and verify every formula matches the glossary."
- "The baseline catches weekends without false-alarming. Robust IQR so incidents don't mask themselves."

---

## Slide 6 — Trustworthiness & Grounding (45 sec)

**Content:**
- LLM gets the ledger and NOTHING else — no raw data, no SQL tool, no freedom
- `grounding.py`: extracts every number from the prose, checks each against the ledger
- **One unmatched number → entire LLM output discarded → templated fallback from the ledger**
- "A missing narrative is cheaper than a fabricated one"

**Visual:** Side-by-side: LLM output vs grounding check result. Show a grounded output and what a fallback looks like.

**What to say:**
- "We don't retry. We don't ask the model to fix itself. We throw it away and use the template."
- "Every number in the diagnosis is reproducible from the data. That's the bar."

---

## Slide 7 — Traceability (Langfuse) (30 sec)

**Content:**
- Every ladder stage + narration wrapped in a Langfuse span
- Each span carries: SQL text, `query_id`, rows read, elapsed time
- One choke point (`clickhouse_client.query_rows`) → single place to instrument
- Trace flushes before the background task exits

**Visual:** Screenshot of a Langfuse trace showing the spans for a real investigation.

**What to say:**
- "A judge can open this trace, read every SQL the system ran, in order, and verify every number."
- "No trace, no credit — that's the rubric, and we take it literally."

---

## Slide 8 — Detection Results (45 sec)

**Content — the confirmed detections table:**

| Day(s) | Segment | Actual | Expected | Peak z |
|---|---|---|---|---|
| Jun 23–25 | `os_version=Android 15` | 0.434 | 0.785 | 28.1 |
| Jun 29–30 | `os_version=iOS 18.1` | 0.683 | 0.780 | 10.6 |
| Jun 23–25 | global fill rate | 0.750 | 0.785 | 11.4 |

- Walk through the Android 15 incident: fill rate dropped → holdout confirmed → dependency walk confirmed OS-level fault
- Mention what was **ruled out**: seasonality, device_model (bleed-through), region (bleed-through)

**Visual:** The RCA UI showing the Android 15 diagnosis.

**What to say:**
- "Four dimensions lit up. Only one survived the holdout. The system named it AND explained why the others were false leads."

---

## Slide 9 — The Unseen Incident (60 sec) ⭐

> This is the highest-weight slide. The judges compare outputs directly across teams.

**Content:**
- Show the system's output for the sealed dataset — **as generated, no editing**
- The diagnosis text
- The key numbers
- The Langfuse trace (or link to it)

**Visual:** Full-screen RCA UI output or the narrative text. Show the trace.

**What to say:**
- "This was generated by our system, untouched. Here's the trace that proves it."
- Walk through: what was found, what was checked, what was ruled out.

**⚠️ CRITICAL:** Have the trace open and ready. No trace = no credit.

---

## Slide 10 — What We Didn't Build (and Why) (30 sec)

**Content:**
- No per-metric agents → one registry-driven agent
- No free-form SQL from the model → fixed parameterised ladder
- No pre-aggregated rollup → one definition, executed
- No external semantic layer → ClickHouse IS the definition store
- Out of scope by design: auth, polished frontend, alerting integrations

**What to say:**
- "We made deliberate trade-offs. Every 'no' was a choice to put analytical depth ahead of scaffolding."

---

## Slide 11 — Summary & What's Next (15 sec)

**Content:**
- **Fast:** Diagnosis in seconds
- **Trustworthy:** Every number computed, grounding-checked, traceable
- **Localized:** Names the segment AND proves it by holdout
- **Honest:** Shows what was checked and cleared

**Close with:** "Alert to answer. Seconds, not days. Every claim backed by a number."

---

## Slide Design Notes

- **Keep slides visual.** Architecture diagrams, screenshots, tables — not paragraphs.
- **Dark theme recommended** — matches the RCA UI and looks professional for a tech demo.
- **Max 2 bullet points per slide** when speaking. Let the visual do the work.
- **Font:** Use a clean sans-serif (Inter, Roboto, or similar).
- **Colour accent:** Use amber/gold for ClickHouse elements, purple for LLM/AI elements, teal for the agent — consistent with the architecture diagram.
