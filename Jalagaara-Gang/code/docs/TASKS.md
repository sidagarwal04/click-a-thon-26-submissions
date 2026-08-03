# Task Board — Automated Root-Cause Analyst

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · **(BLOCKER)** = someone is waiting on this
Assign owners at kickoff. Keep this file updated — it's our single source of truth for status.

---

## Phase 0 — Setup & contract (T+0 → T+1) · ALL

- [ ] Create repo structure (`backend/`, `frontend/`, `fixtures/`), branches per lane
- [ ] `.env.example` with: `CLICKHOUSE_HOST/USER/PASSWORD`, `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`, `LLM_API_KEY`
- [ ] Provision ClickHouse Cloud service (event credits) — capture connection creds **(BLOCKER for A)**
- [ ] Create Langfuse project — capture keys **(BLOCKER for C)**
- [ ] LLM provider key in env
- [ ] **Freeze Evidence Bundle schema** together — walk `contracts/evidence_bundle.schema.json` line by line
- [ ] Author `fixtures/sample_bundle.json` (realistic fake incident) **(BLOCKER for C & D)**
- [ ] Everyone reads PROBLEM_STATEMENT.md + metrics_glossary.md; agree formulas

---

## Lane A — Data & ClickHouse

- [ ] Define `ad_events` schema (types: `event_time DateTime`, `is_* UInt8`, `revenue Float64`, ids as `LowCardinality(String)`) **(BLOCKER)**
- [ ] Load `ad_events.parquet` (9M) + `apps.csv` + `advertisers.csv` + `geo_device.csv`
- [ ] Sanity checks: row count = 9M, date range Jun 1–Jul 5 2026, `NAM` present (not `NA`), empty `advertiser_id` on unfilled
- [ ] Build **`events_full`** — denormalized fact + all dims flattened (single table for drill-downs) **(BLOCKER for B)**
- [ ] Build **hourly rollup** (MV or table): sums of requests/fills/impr/clicks/revenue grouped by hour + every dimension
- [ ] Shared metric SQL snippets (fill_rate, ctr, ecpm, rpr as sum/sum) — one source of truth
- [ ] `run_query(sql, params) -> (rows, logged_sql, elapsed)` helper that returns the exact SQL for `queries[]` **(BLOCKER for B & C)**
- [ ] 100k-row sample table for fast local query dev
- [ ] Reusable **baseline query template** (same weekday + hour, trailing N weeks, median/MAD)
- [ ] Doc: how to connect + reload data from a clean checkout

---

## Lane B — Detection & RCA engine (critical path)

**Detection**
- [ ] Metric time series at hourly grain (uses A's rollup)
- [ ] Robust like-for-like baseline (same weekday/hour, median + MAD over trailing 3wk)
- [ ] Anomaly scorer → `{observed, expected, abs_delta, pct_delta, score, direction, detected}`
- [ ] Threshold tuning so weekends don't fire and the seasonality decoy is NOT alarmed

**RCA — factor decomposition**
- [ ] Compute Requests / FillRate / eCPM for target vs baseline window
- [ ] Log-additive attribution of total delta across factors → `factor_decomposition` + `primary_factor`
- [ ] Flat factors → `ruled_out` entries with numbers

**RCA — segment drill-down**
- [ ] Contribution ranking SQL: for a factor, rank dimension values by `Δ_segment / Δ_total` **(BLOCKER)**
- [ ] Recursive driver: pick top contributor, add to cumulative filter, recurse
- [ ] Stop criterion (marginal contribution threshold / max depth) → `localized_segment`
- [ ] Populate `drilldown[]` with status (culprit/contributor/normal) + `query_id` per node
- [ ] Record cleared dimensions + explicit checks (volume, CTR, device mix, seasonality) into `ruled_out[]`

**Assembly**
- [ ] `build_bundle(...)` assembles a schema-valid Evidence Bundle **(BLOCKER for C & D integration)**
- [ ] Validate output against `evidence_bundle.schema.json` in a test
- [ ] Regression check on ≥3 distinct planted anomalies (different metric/segment)

---

## Lane C — Narrator & Orchestration

- [ ] Langfuse SDK wired; helper to open a trace per `investigation_id`
- [ ] Instrument every SQL as a span (input SQL+params, output result_summary) + narration as a generation span
- [ ] Put `trace_url` back into the bundle **(BLOCKER for D's trace link)**
- [ ] Narrator prompt: input = bundle, output = 3–5 sentence diagnosis, numbers only from bundle, low temp
- [ ] Narration includes the ruled-out list ("checked and cleared: …")
- [ ] **Hallucination guardrail**: extract all numbers from prose, assert each exists in bundle → `narrative_verification` **(BLOCKER — trust score)**
- [ ] FastAPI `POST /investigate {metric, window}` → runs pipeline → returns bundle+narrative+trace_url
- [ ] `GET /health`, CORS for the frontend
- [ ] `POST /chat {question, investigation_id}` → answers from bundle, or issues a scoped follow-up query
- [ ] Works against fixture bundle first, real pipeline after B integrates

---

## Lane D — Dashboard (React + Vite, lean, fixtures-first)

- [ ] Vite + React + TS scaffold; load `fixtures/sample_bundle.json`
- [ ] **Metric tree** component: nodes colored green/amber/red by `status`, path highlighted **(BLOCKER for demo)**
- [ ] Diagnosis card: the narrative + headline delta
- [ ] Factor bar: requests / fill / eCPM contribution split
- [ ] **Ruled-out panel**: checked-and-cleared list with the numbers
- [ ] Trace link → Langfuse `trace_url`
- [ ] Wire live API (`/investigate`) after C exposes it
- [ ] Follow-up chat box → `/chat`
- [ ] Incident replay view for the demo (metric drops → tree lights up → diagnosis)
- [ ] Time-box: stop polishing once it clearly tells the story

---

## Phase 3/4 — Rehearse & submit · ALL

- [ ] End-to-end on ≥3 known anomalies, misses/false-alarms fixed
- [ ] Full dry run of the unseen-incident procedure (load → run → capture trace)
- [ ] ≤500-word solution summary
- [ ] ≤15-slide pitch deck
- [ ] ≤5-min demo video storyboard + recording
- [ ] Repo public + LICENSE (MIT or Apache-2.0), secrets scrubbed
- [ ] **Unseen incident:** load dataset, run, capture diagnosis + numbers + trace URL, include in submission
- [ ] Submit

---

## Standup checklist (every few hours)
1. What's `[x]` since last sync? 2. Any new **(BLOCKER)**? 3. Is `main` still runnable? 4. Are we on the T+7 / T+14 / T+20 marks?
