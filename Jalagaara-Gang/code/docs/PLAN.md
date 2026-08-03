# Master Plan — Automated Root-Cause Analyst

**Team:** Jalagaara Gang (4) · **Event:** Click-a-thon 2026 (InMobi) · **Window:** 24h

## The win condition

We are scored on five things ([full detail](../InMobi/PROBLEM_STATEMENT.md#how-you-will-be-evaluated)):

1. **Detection & localization accuracy** — find the planted anomalies, name the right segment, don't cry wolf.
2. **Explanation trustworthiness** — every number reproducible. *One fabricated figure costs more than a missed anomaly.*
3. **Analytical depth in ClickHouse** — the drill-down is SQL, not LLM.
4. **Traceability** — a judge can follow the investigation. No trace, no credit.
5. **The unseen incident** — our output on fresh, never-seen anomalies. Directly compared across teams. **Carries significant weight.**

**Strategy that maximizes score:** nail #2, #3, #4 first (they're deterministic and fully in our control), then push #1 accuracy, and rehearse the pipeline so #5 is a button-press, not a scramble.

## The architecture, restated

```
ClickHouse (detective, all math)  →  Evidence Bundle (JSON contract)  →  LLM (journalist, prose only)
```

Read [`AGENTS.md`](../AGENTS.md) for the full diagram. The **Evidence Bundle** ([`contracts/evidence_bundle.schema.json`](../contracts/evidence_bundle.schema.json)) is the spine — freeze it in hour 1 and everyone builds against it in parallel.

## The five milestones (your five stages, mapped)

| # | Milestone | What "done" means | Primary lane |
|---|---|---|---|
| M1 | **Data & DB** | Parquet+CSVs in ClickHouse; `events_full` + hourly rollup; helper to run+log SQL | A |
| M2 | **Detection** | Given a metric+window, robust like-for-like baseline says "real move, score X, direction Y" | B |
| M3 | **RCA engine** | Factor decomposition + recursive contribution drill-down → full Evidence Bundle incl. `ruled_out` | B (+A) |
| M4 | **Narrator + Telemetry** | Langfuse trace of the whole run; LLM diagnosis with hallucination guardrail; ruled-out surfaced | C |
| M5 | **Dashboard** | Metric tree lights green/amber/red; diagnosis + ruled-out panels; trace link; follow-up chat | D |

M3 is the heart. M2→M3→M4 is the critical path. M1 unblocks everything; M5 runs alongside on fixtures.

## How the algorithm actually works (so everyone shares one mental model)

**Detection.** For the target metric at hourly grain, build a baseline from the *same weekday and hour over the trailing 3 weeks* using median + MAD. Flag if the observed value's robust z-score exceeds a threshold. This kills weekend false-positives and lets the *pure-seasonality decoy* be ruled out cleanly.

**Step 1 — which FACTOR moved?** Walk the revenue identity `Revenue ≈ Requests × FillRate × eCPM/1000` with a log-additive decomposition. Attribute the total delta across `requests` (volume), `fill_rate`, `ecpm` (price). Whichever factor carries most of the delta is `primary_factor`. The others, if flat, become `ruled_out` entries ("request volume normal", etc.).

**Step 2 — which SEGMENT?** For the responsible factor, rank every value of each dimension by its **contribution to the total delta** (`Δ_segment / Δ_total`). Take the top-contributing dimension+value, add it to the cumulative filter, and **recurse**: within that segment, split by the next dimension, rank again. Stop when the next split's top contributor no longer explains a meaningful share (marginal contribution below threshold) — that's the localized culprit, e.g. `country=IN ∧ os=Android ∧ app=app_00123`.

**Ruled-out (the trust builder).** At every level, dimensions whose slices are all near baseline get recorded as checked-and-cleared with their number. Also explicitly check and clear: request volume, CTR/quality, device mix, and seasonality.

**Output.** Every scalar above comes from a named, logged SQL query. They all land in the Evidence Bundle's `queries[]`. The narrator reads the bundle and writes 3–5 sentences. A guardrail extracts every number from the prose and asserts it exists in the bundle.

## 24-hour timeline

> Times are hours from kickoff (T+0). Adjust at standup. **The two hard sync points are the contract freeze (T+1) and integration (T+7).**

### Phase 0 — Setup & contract (T+0 → T+1) · everyone
- Repo, branches, `.env.example`, ClickHouse Cloud service up, Langfuse project up, LLM key in env.
- **Freeze the Evidence Bundle schema together.** Hand-author [`fixtures/sample_bundle.json`](../fixtures/sample_bundle.json) — a realistic bundle for a fake "revenue drop in IN/Android" incident. This unblocks C and D immediately.
- Read the problem statement + glossary. Agree metric formulas.

### Phase 1 — Parallel vertical slices (T+1 → T+7)
- **A:** load all four files; build `events_full` + hourly rollup; ship `run_query(sql, params) -> (rows, logged_sql)` helper. **Deliver a working DB by T+3** — B is blocked without it.
- **B:** prototype detection + one level of contribution drill-down as raw SQL in the ClickHouse console against real data; port to Python; start emitting a partial bundle.
- **C:** against the fixture bundle — Langfuse tracing scaffold, narrator prompt + guardrail, FastAPI `/investigate` returning the bundle. Swap in real pipeline later.
- **D:** against the fixture bundle — metric tree, diagnosis card, ruled-out card, trace link. No backend dependency.

### Phase 2 — Integration (T+7 → T+14)
- Wire B's real bundle through C's narrator + trace into D's dashboard. **End-to-end on a KNOWN planted anomaly.**
- Tune: baseline thresholds, drill-down stop criterion, contribution ranking. Verify the ruled-out list is honest and the seasonality decoy is cleared, not alarmed.
- Guardrail must pass on real output.

### Phase 3 — Harden & rehearse (T+14 → T+20)
- Run against several different planted anomalies (different metrics/segments) to prove generalization. Fix misses and false alarms.
- Follow-up chat: "why not device X?" answered from the bundle / a fresh scoped query.
- Freeze code paths. Write the ≤500-word summary, draft the ≤15-slide deck, storyboard the ≤5-min demo.

### Phase 4 — Unseen incident + submission (T+20 → T+24)
- **Unseen dataset drops** (time announced at kickoff). Load it, run the pipeline, capture: diagnosis + numbers + **Langfuse trace URL**. This is the highest-weight deliverable — do it calmly because we rehearsed.
- Record demo video, finalize deck + summary, make repo public (MIT/Apache-2.0), submit.

## Risk register

| Risk | Mitigation |
|---|---|
| Data load / ClickHouse setup eats hours | A starts at T+0, hard deadline T+3, load a 100k-row sample first to unblock query dev |
| Contract churn blocks parallelism | Freeze schema at T+1; changes only by team agreement |
| Drill-down over-fits the known anomaly | Test on ≥3 distinct anomalies in Phase 3; no hardcoding (enforced in review) |
| LLM invents numbers | Guardrail rejects any number not in the bundle; narrator temp low |
| Unseen incident scramble | Full rehearsal in Phase 3 so Phase 4 is a replay |
| Over-building the UI | Time-box Lane D; fixtures-first; judges deprioritize polish |

## Definition of a submittable system

- [ ] One command runs an investigation end-to-end and returns a bundle + narrative + trace URL.
- [ ] Works on an anomaly we've never special-cased.
- [ ] Every number in the diagnosis is in `queries[]` and the guardrail passes.
- [ ] Langfuse shows the full investigation trace.
- [ ] Dashboard replays an incident: tree → diagnosis → ruled-out → trace.
- [ ] Public repo, ≤500-word summary, ≤5-min video, ≤15-slide deck, unseen-incident output + trace.
