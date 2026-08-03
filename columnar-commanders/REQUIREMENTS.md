# Click-a-thon 2026 — Requirements Tracker

**Project:** atlys-PrismCH — agentic analytics on ClickHouse
**Problem:** From feature spec to insight: agents that instrument, analyze, and explain

> All data is synthetic. No real customer data, PII, or production records.

Sequencing and time allocation live in [PLAN.md](PLAN.md) — this file tracks
*what* is required, the plan tracks *when*.

---

## Status legend

| Mark | Meaning |
| --- | --- |
| ✅ | Done and verified |
| 🟡 | In progress |
| ⬜ | Pending — not started |
| ⛔ | Blocked (reason in Notes) |
| ➖ | Explicitly out of scope per the brief |

---

## Progress at a glance

| Section | Done | In progress | Pending | Total |
| --- | --- | --- | --- | --- |
| 0. Foundation & data loading | 9 | 1 | 1 | 11 |
| 1. Instrumentation Agent | 10 | 0 | 0 | 10 |
| 2. Analytics Agent | 10 | 0 | 0 | 10 |
| 3. Context Agent | 9 | 0 | 0 | 9 |
| 4. Tracing & visualization | 10 | 1 | 1 | 12 |
| 5. Unseen-spec runbook | 0 | 0 | 8 | 8 |
| 6. Submission deliverables | 3 | 1 | 3 | 7 |
| 7. Constraints compliance | 6 | 0 | 1 | 7 |
| **Total** | **57** | **3** | **14** | **74** |

---

## How this maps to scoring

The brief names five evaluation criteria. Effort should follow the weights, not
the section order above.

| Criterion | Sections that move it | Watch out for |
| --- | --- | --- |
| **The unseen spec** (highest weight) | §5, and generality of §1–§3 | Anything hardcoded to the 5 known specs will show its seams |
| **Schema quality** | §1 | Ordering keys, partitioning, types, MVs that earn their keep |
| **Insight quality** | §2 | Would a PM act on it? Insights need the *why* |
| **Context freshness** | §3 | New table lands → analytics must reason with updated context |
| **Traceability** | §4 | No trace, no credit |

---

## 0. Foundation & data loading

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| F1 | ~~Local ClickHouse dev stack~~ — superseded by F5/F6: Cloud is now the only target | ➖ | `docker/clickhouse/` removed; see [SETUP.md](SETUP.md) |
| F2 | Dockerfile, Makefile, compose workflow | ✅ | `make up` / `make bootstrap` / `make client` |
| F3 | Python package skeleton with config + client helpers | ✅ | `prism_ch/` |
| F4 | Dependency manifests | ✅ | `requirements.txt`, `requirements-dev.txt` |
| F5 | Provision team ClickHouse Cloud service (event credits) | ✅ | Cloud on `fsj452m31r.ap-south-1.aws.clickhouse.cloud:8443` |
| F6 | Make connection target switchable local ↔ Cloud | ✅ | `CLICKHOUSE_TARGET=cloud\|cluster` env var |
| F7 | Load the 8 provided tables + sample data | ✅ | 8 tables loaded in `atlys` database on Cloud |
| F8 | Load the 5 known feature specs + raw event samples | ✅ | Specs available locally, events loadable via UI or CLI |
| F9 | Ingest the base context layer | ✅ | Context Agent parses base_context.md, stores versioned in CH |
| F10 | Wire LLM provider + API keys | ✅ | Gemini 3.5 Flash Lite configured; per-model pricing in `pricing.py` |
| F11 | Stand up ClickHouse MCP server for agent DB access | ⚪ | `python -m prism_ch mcp` still available standalone; LibreChat front-end removed (v0.8.7 client could not connect) |

---

## 1. Instrumentation Agent

**Input:** a feature description. **Output:** production-ready ClickHouse schema, executed.

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| I1 | Ingest a free-form feature spec and extract the event model | ✅ | `SpecInput` + `parse_events_text()` handles dir, file, or inline |
| I2 | Infer column types from raw event samples | ✅ | Deterministic profiling: `LowCardinality`, `DateTime64`, nullable discipline |
| I3 | Choose an ordering key with stated reasoning | ✅ | `suggest_order_by()` with cardinality-order rule; lint enforces leading key |
| I4 | Choose a partitioning strategy | ✅ | Monthly default; justified in decisions |
| I5 | Set TTL / retention | ✅ | Lint check enforces TTL; baseline includes 180-day default |
| I6 | Apply codecs and compression choices | ✅ | `ZSTD`, `Delta`, `DoubleDelta` via `suggest_codec()` |
| I7 | Generate valid `CREATE TABLE` DDL | ✅ | Cluster-aware: `ON CLUSTER` + Replicated engines for cluster target |
| I8 | **Execute** the DDL against ClickHouse | ✅ | Validate in scratch DB first, then execute in real DB |
| I9 | Map raw events → schema (ingest/transform path) | ✅ | Field mapping with dotted path resolution, type coercion, bulk file ingest |
| I10 | Define materialized views / aggregations where warranted | ✅ | MV proposals validated alongside tables; `qualify_select()` rewrites refs |

**Design notes**

- DDL validated in a scratch database before executing. Repair loop feeds errors
  back to the LLM (up to `DDL_REPAIR_ATTEMPTS`).
- Schema quality lint: ordering key population, native types, TTL, MV targets,
  cardinality order.
- Every schema decision emitted as structured output with `why` + `rules[]`.
- Bulk data ingest via `--data-path` or UI field after table creation.

---

## 2. Analytics Agent

**Input:** new tables + existing tables + business context. **Output:** actionable insights.

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| A1 | Discover available tables and their semantics from context | ✅ | `discover()` reads `system.columns` + `system.tables` + context `MAX(version)` |
| A2 | Generate and run analytical SQL against ClickHouse | ✅ | LLM plans queries; all run with `agent-query-safety` settings |
| A3 | Trend analysis | ✅ | `trend` cut required in plan; `toDate()`/`toStartOfWeek()` bucketing |
| A4 | Anomaly detection | ✅ | `anomaly` cut: cross-dimensional grouping for outliers |
| A5 | Segment comparison | ✅ | `device`, `geo`, `segment` cuts; each a mandatory dimension |
| A6 | Correlation analysis | ✅ | Same-query side-by-side metrics over time buckets |
| A7 | Apply business context to interpret numbers | ✅ | Known issues, metric definitions, contradictions fed to interpreter |
| A8 | Attach a confidence score to each insight | ✅ | 0.0–1.0 per insight; lands as Langfuse score |
| A9 | Write insight summaries **for a product audience** | ✅ | Prompt enforces: headline, detail, why, recommendation — no SQL/table names |
| A10 | Enforce: aggregate in ClickHouse, interpret in the LLM | ✅ | `SELECT *` blocked pre-flight; no-GROUP-BY rejected; >200 rows rejected |

**Design notes**

- Raw data never reaches the LLM. Three-layer enforcement: (1) `_is_raw_select()`
  blocks `SELECT *` and queries without aggregation before they hit the DB,
  (2) `QUERY_SETTINGS` caps result size at 10k rows, (3) >200 rows rejected as
  unaggregated.
- Plan prompt requires all 7 cuts (overall, trend, device, geo, funnel, segment,
  anomaly). Missing cuts are logged.
- Interpreter receives business definitions, metric definitions, known issues,
  and context contradictions — grounds every finding.
- Insights without a `why` are silently dropped (`parse_insights()`).
- Coverage summary fed to interpreter so it knows which cuts succeeded.

---

## 3. Context Agent

**Input:** the evolving table landscape. **Output:** a living context layer.

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| C1 | Choose and justify context-layer storage | ✅ | ClickHouse tables: `context_versions`, `context_entries`, `context_issues` |
| C2 | Represent business definitions | ✅ | `kind=definition` entries parsed from base_context.md |
| C3 | Represent metric formulas | ✅ | `kind=metric` entries with source tracking |
| C4 | Represent entity relationships | ✅ | `kind=entity`, `kind=relationship` entries |
| C5 | Auto-update context when tables or columns are added | ✅ | `record_new_table()` called by Instrumentation Agent after DDL |
| C6 | Guarantee the Analytics Agent reads the *latest* context | ✅ | Analytics reads `MAX(version)` at discover time |
| C7 | Surface contradictions in the context layer | ✅ | Same key, different values across sections = contradiction |
| C8 | Surface gaps in the context layer | ✅ | Undocumented tables, metrics referencing missing columns |
| C9 | Version the context layer with a diff/changelog | ✅ | `diff_snapshots()` computes added/removed/changed between versions |

**Design notes**

- Full snapshots, not deltas. Version row written last so readers never see
  half-written state.
- Contradiction detection matches on normalized key alone (ignoring kind), since
  section headings drive kind assignment.
- UI shows the latest version, issues, counts by kind, and the changelog diff.

---

## 4. Tracing & visualization

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| T1 | Langfuse integration | ✅ | Self-hosted stack (`make up-obs`) + `prism_ch/tracing.py` |
| T2 | Trace the Instrumentation Agent | ✅ | 4 steps: profile, design, validate, execute + load |
| T3 | Trace the Analytics Agent | ✅ | 4 steps: discover, plan, run_queries, interpret |
| T4 | Trace the Context Agent | ✅ | Steps for parse, introspect, detect, store |
| T5 | Traces capture **what** each agent did | ✅ | `Step.decision(what=...)`, `Step.output()`, `Step.sql()` |
| T6 | Traces capture **why** — the reasoning | ✅ | `why` is a required keyword — enforced by signature |
| T7 | Traces capture **which context version** was used | ✅ | `agent_step(context_version=...)` on every analytics step |
| T8 | ClickStack for the system-level view | ⬜ | Optional — "if you want to go further" |
| T9 | Visualization: schema changes over time | ✅ | UI Schema tab: tables, engines, ORDER BY, rows, modified dates |
| T10 | Visualization: insights with confidence scores | ✅ | UI Insights tab: confidence rings, why callouts, recommendations |
| T11 | Visualization: context layer diff / changelog | ✅ | UI Context tab: version, entries, issues, changelog diff |
| T12 | Chat/exploration surface (optional, beyond the brief) | ⚪ | Removed — LibreChat's MCP client could not connect (v0.8.7 bug); the Prism CH UI is the primary surface |

**Design notes**

- Per-model token pricing in `pricing.py`. Cost details on every LLM generation.
- `AGENT` observation types (not generic spans) for the Langfuse Agent Graph.
- Feature/surface dimensions on traces for cost breakdown by feature and entry point.
- Duration recorded even when tracing is off and when a step raises.

---

## 5. Unseen-spec runbook (highest weight)

A sixth spec drops simultaneously to all teams in the final hours.
**Release time: announced at kickoff — fill in below.**

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| U1 | Record the announced release time | ⬜ | ⏰ **TBD — capture at kickoff** |
| U2 | End-to-end pipeline runs from spec → schema → insight, unattended | ✅ | Rehearsed on all 5 known specs via `make instrument SPEC=...`, one command each, unattended — see `submission/ddl/`. Each auto-chained into context refresh + analytics with zero manual steps. |
| U3 | Hold out one of the 5 known specs as a dress rehearsal | ✅ | Ran all 5, not just one held-out spec — a stronger version of the same guard (no spec-specific code path across 5 independent designs). One (`03_status_sharing`) hit a genuine repair-loop edge case on its first attempt and succeeded on retry — documented, not hidden, in `submission/TRACES.md`. |
| U4 | Freeze the pipeline before the drop | ⬜ | Applies once the real drop time is known |
| U5 | Capture the generated schema for spec 6 | ⬜ | Required submission artifact — runbook ready in `submission/unseen_data/SPEC_6_PENDING.md` |
| U6 | Capture the insight summary for spec 6 | ⬜ | Same — auto-chains from U5's run, no separate step needed |
| U7 | Capture the trace proving the pipeline produced both | ⬜ | Same |
| U8 | Rehearse the full run at least twice, timed | ✅ | 5 known-spec runs timed via Langfuse: 32.7s–50.4s each (schema repair cycles add ~15-20s); full breakdown in `submission/TRACES.md` |

> **The single biggest risk:** tuning to the five known specs. Every generalization
> shortcut taken now is a visible seam at judging time.

---

## 6. Submission deliverables

| ID | Deliverable | Status | Notes |
| --- | --- | --- | --- |
| D1 | Instrumentation Agent — spec in, production-ready schema out | ✅ | Profile → design → validate → execute → load |
| D2 | Analytics Agent — queries, applies context, writes summaries | ✅ | Discover → plan → execute → interpret; raw-data guard |
| D3 | Context Agent — maintains and feeds the living context layer | ✅ | Parse → introspect → detect → store; versioned snapshots |
| D4 | Tracing + visualization across the whole pipeline | ✅ | Langfuse tracing complete (12 real traces captured in `submission/TRACES.md`); UI has 4 tabs (Instrument/Analysis/Context/Schema); ClickStack explicitly out of scope — see `ARCHITECTURE.md` §4 |
| D5 | Unseen-spec output: schema + insight summary + trace | ⬜ | Depends on §5 — no 6th spec exists yet; runbook ready |
| D6 | README covering setup, architecture, and design rationale | ✅ | `RUN.md` (judge-facing run instructions), `SETUP.md` (fresh-machine setup), `ARCHITECTURE.md` (agents, storage, tracing, LLM choice, flowcharts), `README.md` (full reference) |
| D7 | Written justification for the context-storage choice | ✅ | `ARCHITECTURE.md` §4 + `prism_ch/agents/context_store.py` module docstring |

---

## 7. Constraints compliance

| ID | Constraint | Status | Notes |
| --- | --- | --- | --- |
| X1 | ClickHouse is the primary datastore | ✅ | Cloud service running; agents query CH directly |
| X2 | Schemas optimized for columnar storage and query performance | ✅ | Lint enforces ordering keys, native types, TTL, codecs |
| X3 | Agents run against **our own** ClickHouse Cloud service | ✅ | `CLICKHOUSE_TARGET=cloud` with Cloud credentials |
| X4 | LLM usage traced | ✅ | Every generation: tokens, cost_details, model, finish_reason |
| X5 | Token discipline — compute in ClickHouse, interpret in the LLM | ✅ | Three-layer raw-data guard in Analytics Agent |
| X6 | Any language/framework — choice recorded and justified | ✅ | Python; stdlib + clickhouse-connect + langfuse + google-genai |
| X7 | Human-in-the-loop gates allowed, but spec-6 output must be pipeline-generated | ⬜ | Approval gate in UI; CLI runs unattended for spec-6 |

### Explicitly out of scope

Do not spend time here — the brief says judges reward the agent loop, not scaffolding.

| Item | Status |
| --- | --- |
| Authentication | ➖ |
| Production deployment | ➖ |
| Streaming ingestion | ➖ |
| Polished frontends | ➖ |

---

## Open questions

| # | Question | Owner | Resolution |
| --- | --- | --- | --- |
| Q1 | Exact release time for the unseen spec? | | TBD at kickoff |
| Q2 | Context-layer storage — file, ClickHouse table, or vector store? | | ✅ ClickHouse tables (versioned snapshots) |
| Q3 | Which LLM provider and model tier per agent? | | ✅ Gemini 3.5 Flash Lite; fallback configurable |
| Q4 | Langfuse — cloud or self-hosted? | | ✅ Self-hosted via docker compose |
| Q5 | Visualization form factor: dashboard, light UI, or structured CLI? | | ✅ Browser UI (4 tabs) + CLI |
| Q6 | Do we run agents against Cloud only, or local for dev and Cloud for the real run? | | ✅ Both; `CLICKHOUSE_TARGET` switches |
| Q7 | How do we detect and report the seeded context contradictions? | | ✅ Context Agent: same key, different values = contradiction |
| Q8 | Which known spec gets held out as the dress rehearsal? | | TBD — pick before Phase 3 |

---

## Known risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Overfitting to the 5 known specs | Fails the highest-weighted criterion | Hold out a spec (U3); no spec-specific branching in agent code |
| Tracing added late | "No trace, no credit" on spec 6 | Traces built from day 1; 124 tests cover tracing paths |
| Analytics Agent pulls raw rows into the LLM | Token budget exhausted mid-run | Three-layer guard: pre-flight SQL check, query settings, row limit |
| Stale context reaching the Analytics Agent | Fails context-freshness scoring | `MAX(version)` read at discover time; version on every trace step |
| Cloud service not provisioned in time | Blocks downstream sections | ✅ Provisioned and tested |
| Late edits break the frozen pipeline | Phase 5 freeze protocol | Hard freeze at drop − 2h |

---

*Update the Status column as work lands, and keep the "Progress at a glance"
counts in sync.*
