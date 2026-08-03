# AGENTS.md — Jalagaara Gang · Click-a-thon 2026

> Read this before writing a line of code. It is the shared brain for every human **and** every AI agent on this repo. If your change contradicts this file, the file wins — or you change the file first and tell the team.

## What we are building (one sentence)

An **automated root-cause analyst**: it detects when an ad metric (revenue, fill rate, CTR…) deviates from its baseline, **drills down in ClickHouse** to name the exact segment responsible, and emits a **plain-language diagnosis where every number is real and computed** — including what it checked and *ruled out*.

The problem statement lives in [`InMobi/PROBLEM_STATEMENT.md`](InMobi/PROBLEM_STATEMENT.md). Metric formulas in [`InMobi/metrics_glossary.md`](InMobi/metrics_glossary.md). **Read both once.** They are the source of truth for how we're judged.

## The one idea that wins this

> **ClickHouse is the detective. The LLM is the journalist.**

Deterministic SQL does 100% of the analysis and produces every number. The LLM only turns those numbers into English. A system that streams raw events into an LLM will be *slow, expensive, and will invent numbers* — and a single fabricated number costs us more than a missed anomaly. Never let the model do arithmetic on data.

## Architecture (data flows top to bottom)

```
  Parquet + CSVs
        │  (load once)
        ▼
  ClickHouse Cloud  ──  events_full (denormalized fact+dims) + hourly rollup
        │
        ▼
  Detection        ──  same-weekday/hour baseline, robust z-score → is this a real move?
        │
        ▼
  RCA Engine       ──  (1) factor decomposition via revenue identity
        │               (2) recursive contribution drill-down by dimension
        │               ALL in ClickHouse SQL. Emits the Evidence Bundle.
        ▼
  Evidence Bundle (JSON)  ──  contracts/evidence_bundle.schema.json  ← THE contract
        │
        ▼
  Narrator (LLM, Langfuse-traced) ── prose from bundle numbers only + hallucination guardrail
        │
        ▼
  FastAPI  ──  Dashboard (React): metric tree green/amber/red · diagnosis · ruled-out · chat
```

## The central contract

Everything hinges on **[`contracts/evidence_bundle.schema.json`](contracts/evidence_bundle.schema.json)**. The RCA engine *produces* it; the Narrator and Dashboard *consume* it. **Agree on it in hour 0 and freeze it early.** Once it's stable, all four workstreams build in parallel against it — the RCA team against real ClickHouse, the Narrator and Dashboard teams against a fixture bundle. Change the schema only by team agreement, and bump nothing silently.

## Chosen stack (decided — don't re-litigate mid-hackathon)

| Layer | Choice | Notes |
|---|---|---|
| Datastore + analytical engine | **ClickHouse Cloud** | Mandatory. All analysis is SQL here. |
| Backend | **Python 3.11+** | `clickhouse-connect`, `fastapi`, `uvicorn`, `pydantic`, `pandas` (baselines only). |
| LLM observability | **Langfuse** | Our required integration. Every investigation = one trace; every SQL = a span. This is the "no trace, no credit" deliverable. |
| LLM | Any provider via key in env | Narration only. Cheap model is fine. |
| Frontend | **React + Vite + TypeScript** | Lean. Judges deprioritize polished UI — time-box it. |
| Package mgmt | `uv` (py) / `pnpm` (js) | Use lockfiles. |

## Workstream ownership (4 people, 4 lanes)

| Lane | Owner | Deliverable | System prompt |
|---|---|---|---|
| **A — Data & ClickHouse** | | schema, load, `events_full`, rollups, query helpers | [`prompts/01-data-clickhouse.md`](prompts/01-data-clickhouse.md) |
| **B — Detection & RCA** | | baseline detection + factor decomposition + drill-down → Evidence Bundle | [`prompts/02-detection-rca.md`](prompts/02-detection-rca.md) |
| **C — Narrator & Orchestration** | | Langfuse tracing, LLM narrator + guardrail, FastAPI | [`prompts/03-narrator-orchestration.md`](prompts/03-narrator-orchestration.md) |
| **D — Dashboard** | | metric tree, diagnosis + ruled-out panels, chat, trace link | [`prompts/04-dashboard.md`](prompts/04-dashboard.md) |

Fill in the Owner column at kickoff.

## Working with your AI agent (all lanes)

- **Ground it.** Point your agent at this file, your lane's prompt, the problem statement, and the Evidence Bundle schema before asking for code.
- **Keep it in its lane.** Your agent works on your subtree. Don't let it refactor another lane's files — coordinate in chat instead.
- **Verify before you claim done.** Run it. Show the output. "It should work" is not done. See [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md).
- **Numbers are sacred.** If your agent writes code that lets the LLM compute or guess a metric, that's a bug, not a feature.

## Non-negotiables (these are how we're scored)

1. **Every number is reproducible from a SQL query in `queries[]`.** No exceptions.
2. **Baselines are like-for-like** (same weekday/hour, trailing weeks) — never a flat average. At least one planted anomaly is *pure seasonality* and must be **ruled out, not alarmed on**.
3. **The trace is a deliverable.** If Langfuse doesn't show the investigation, it didn't happen (per judges: "No trace, no credit").
4. **Build for the unseen incident**, not the anomalies we find during the build. No hardcoding segment names, thresholds tuned to one incident, or answer-key peeking.
5. **`NAM` not `NA`** for North America. `advertiser_id` is empty on unfilled requests.

## Repo layout

```
├── AGENTS.md                     ← you are here
├── docs/
│   ├── PLAN.md                   ← master plan + 24h timeline
│   ├── TASKS.md                  ← the task board
│   └── CODING_STANDARDS.md       ← how we write code
├── contracts/
│   └── evidence_bundle.schema.json   ← THE interface
├── prompts/                      ← per-lane system prompts for your agents
├── InMobi/                       ← the problem + data (do not edit)
├── backend/                      ← python: data, rca, narrator, api  (lanes A/B/C)
├── frontend/                     ← react + vite                       (lane D)
└── fixtures/
    └── sample_bundle.json        ← a hand-authored Evidence Bundle so C & D unblock on day 1
```

## Ground rules

- Branch per lane (`lane-a-data`, `lane-b-rca`, …). Small PRs. `main` stays runnable.
- Secrets in `.env` (gitignored). Commit `.env.example`. Never commit keys — the repo goes public (MIT/Apache-2.0).
- All code written inside the 24h window (rule). Setup/reading now is fine.
