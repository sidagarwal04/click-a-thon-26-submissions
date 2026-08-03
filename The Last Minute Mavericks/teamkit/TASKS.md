# Task Board — 3 people, 4 terminals, 12 hours

Scope: **revenue only**, decomposed through fill_rate + eCPM. Depth on one metric tree beats a
generic framework. Each terminal = one git worktree = one directory = no file conflicts.

## Role split (from our own strategy chat)
- **A — ClickHouse owner** (`sql/`). Schema, cube, all analysis SQL. Highest-leverage seat —
  25% of the score is "is ClickHouse genuinely central." Barely touches Python.
- **B — Orchestration + trust** (`agent/` + `run_incident.py`). LangGraph, evidence store,
  validator, narration prompt, Langfuse wiring. Owns the trust layer that wins the demo.
- **C — Integrations, then deliverables** (`integrations/` → `ui/` → video/deck/summary).
  **From ~hour 8, C does nothing but the deliverables.** This is the seat people fumble.
- 4th terminal = floating capacity: B runs `agent/` in one and builds `run_incident.py` +
  tests in the other; hand to A for parallel SQL when the cube is stable.

## Phase 0 — Setup sprint · first 60 min · TOGETHER, not parallel
The most important hour. Getting the contracts frozen is what makes the rest conflict-free.
- [ ] Captain: create the team ClickHouse Cloud service (venue signup link) → creds into shared `.env`.
- [ ] GitHub repo **public + MIT from commit one**. Commit `CLAUDE.md`, `CONTRACTS.md`, this file.
- [ ] Verify the data at the source before trusting any SQL: **event-level or pre-aggregated?**
      Does `revenue` sit on impression rows or separate events? (Changes the cube MV.)
- [ ] Load the 4 files; confirm 9M rows. Paste A's `01_schema.sql` (the "Rca clickhouse" artifact
      from our chat — copy it out; column names in section 0 adjust to the real file).
- [ ] **Freeze CONTRACTS.md**, especially the Evidence Store + Bundle. Commit `example_bundle.json`.
- [ ] Langfuse up (Cloud or self-host — pull Docker images beforehand). Keys → `.env`.
- [ ] `setup.sh`: 4 worktrees, one per terminal.

## Phase 1 — Dumb end-to-end FIRST · ~hour 1–2
**Build `run_incident.py <path>` before any clever part.** ingest → detect (naive top-segment)
→ printed sentence → trace bundle. One command, works end to end on a stupid baseline. Commit.
Everything after this just makes a stage smarter. **Schema-tolerant loader: read column names
from the file, don't hardcode.**

## Phase 2 — Parallel build · ~hour 2–7 (against frozen contracts)
### A · `sql/`
- [ ] Cube (AggregatingMergeTree MV). MAD z-score detection MV (same-hour-last-week median).
- [ ] LMDI decomposition. Adtributor (EP + JS-surprise). Simpson's exclusion check. Ruled-out ledger.
- [ ] Over-detection gates: min-volume floor + EP floor + confidence.
### B · `agent/`
- [ ] LangGraph: detect → decompose → attribute → descend → verify → rule_out → narrate.
- [ ] Evidence store (`register→ev_id`). Validator (reject unresolved numerals, retry once).
- [ ] Narration prompt: label/value pairs in, `{{ev_N}}` placeholders out.
- [ ] Langfuse span per node (SQL, `query_id`, rows, prune reason). `inject_hallucination` toggle.
### C · `integrations/` (until ~hour 7, then stop and switch to UI)
- [ ] Langfuse verified end to end (spine — do first).
- [ ] LibreChat: expose the graph as OpenAI-compatible `/v1/chat/completions`, register as custom endpoint.
- [x] ClickStack: OTel-instrument the service → HyperDX (per-stage latency + a span per ClickHouse query). Plan + measured results: `PLAN_CLICKSTACK.md`.

## Phase 3 — Integrate + harden · ~hour 7–9
- [ ] End-to-end on SEEN data for 3–4 known anomalies. Every narrated number reproduces from SQL.
- [ ] Demo the validator rejecting a tampered narration. Confirm the trace reads like a story.
- [ ] Test `run_incident.py` on a **hand-mangled** copy of the data (unseen-incident rehearsal).
- [ ] C builds the UI: one Streamlit page, 5 panels (see DEMO.md), build order = panel 1→5.

## Phase 4 — Deliverables · ~hour 9–11 · C leads, solo
- [ ] **Full dry submission by hour 10** — all fields, real URLs, placeholder video/deck, then swap.
- [ ] 500-word summary · ≤5-min demo video · ≤15-slide PDF deck. Record early, not at the deadline.

## Phase 5 — Unseen incident + freeze · last hour
- [ ] Dataset drops → `run_incident.py <new>` → save diagnosis + trace_id + screenshots → attach.
- [ ] Submit with a 30-min buffer. Portal closes server-side at 12:00 IST, no extensions.

## Conflict + hygiene rules
- Edit only your own directory. `contracts/` + `CLAUDE.md` change by announcement only.
- Trunk-based: push every ~45 min; `main` stays runnable. Two agents needing one file = a missing contract.
- **Pause the ClickHouse service when you step away** — idle burns the $400.
- The LLM never sees a raw row and never does arithmetic. If you're about to pass a dataframe into a prompt, stop.
```
