# Gap Analysis: `atlys_tech_design.md` vs. Click-a-thon 2026 Problem Statement

**Scope:** Line-by-line comparison of the Technical Design Document against `PROBLEM_STATEMENT.md`, `README_START_HERE.md`, `base_context.md`, `data/ddl.sql`, `data/instrumentation_notes.md`, and all 5 `specs/*/spec.md` + `events.ndjson` samples.
**Verdict:** The design is directionally sound (CrewAI + ClickHouse Cloud + chDB + Langfuse) but is not yet submission-ready. It fails or under-specifies 3 of the 5 judged criteria, is silent on the highest-weighted criterion (the unseen 6th spec), and does not account for several concrete data quality issues present in the actual dataset. Section 3 below is a required-fix checklist.

---

## 1. Scorecard Against the 5 Evaluation Criteria

| # | Criterion (from `PROBLEM_STATEMENT.md` §"How you will be evaluated") | Design Doc Status | Verdict |
|---|---|---|---|
| 1 | **Schema quality** — ordering keys, partitioning, column types, MVs earning their keep | Only says "using proper `ORDER BY` and Partition keys" — no heuristic, no TTL, no MV strategy, no dedup handling | **Fail** — nothing a judge can inspect beyond a generic instruction to the LLM |
| 2 | **Insight quality** — carries the *why*, PM-actionable | `Product Analyst` synthesizes "Deliverable Insight formatted text" — no template, no confidence score, no explicit "why" requirement wired into the task/tool | **Partial** |
| 3 | **Context freshness** — Analytics Agent reasons from *updated* context, not a stale snapshot | `Context Librarian` only *reads* `chDB` (JIT SQL fetch of `base_context.md` chunks). Nothing writes new schema/table facts back after CUJ 1 runs | **Fail** — the design has no write-back path, so context is frozen at whatever `base_context.md` said at t=0 |
| 4 | **Traceability** — full reasoning chain, "no trace, no credit" | Langfuse is wired via LiteLLM callbacks — good — but no mention of how trace IDs are captured, exported, or attached to the deliverable outputs judges will read | **Partial** |
| 5 | **The unseen 6th spec** — carries "significant weight," proof-by-trace required | **Not mentioned anywhere in the document.** No CUJ, no SLA, no fallback for the live Day-2 event window | **Fail — highest-weighted criterion, zero coverage** |

---

## 2. Deliverables Checklist (literal list from the problem statement)

| Deliverable | Present in design? | Note |
|---|---|---|
| 1. Instrumentation Agent — spec in, prod-ready schema out | Yes (component + agent defined) | Missing heuristics (see §3.2) |
| 2. Analytics Agent — query + context + insight summary | Yes | Missing statistical rigor, confidence scores, PM-audience template |
| 3. Context Agent — living context layer, feeds other agents | **No** — only a read-only retriever, not a maintainer | Renamed/rescoped required |
| 4. Tracing + **visualization layer** (schema changes, insights w/ confidence, context diff/changelog) | Tracing yes, **visualization layer entirely absent** | New component required |
| 5. Output for the unseen 6th spec + trace proving pipeline origin | **No** | New CUJ + operational runbook required |

---

## 3. Detailed Gaps by Component

### 3.1 Instrumentation Agent / Instrumentation Engineer

- **No heuristic for `ORDER BY`/`PARTITION BY`/`TTL` choice.** The doc says the agent designs "highly optimized columnar schemas" but gives no rule (e.g., cardinality-ascending column order, time-based partitioning, cold-data TTL). Judges score this explicitly — the doc must state the actual heuristic the LLM is prompted with, or a deterministic tool that computes it.
- **No TTL clause anywhere.** `Tool_Execute_DDL` only mentions `CREATE TABLE` / `MATERIALIZED VIEW`. TTL is a named judging axis and is entirely absent from the LLD.
- **The existing 8 tables use a legacy anti-pattern the design must not repeat.** `base_context.md` §3 and `data/instrumentation_notes.md` both flag: `ORDER BY (id, timestamp, user_id)` — sorted by a UUID first — while "queries filter by time/segment, never by `id`." This is called out as a known flaw ("a legacy of the event-table template"). The design doc must explicitly state that new tables use `ORDER BY (<segment/date>, user_id, timestamp)`-style keys instead, or a judge will assume the agent blindly copied the broken pattern.
- **No handling of nested JSON in raw events.** `specs/01_express_checkout/events.ndjson` has a nested `payment` object (`payment.amount`, `payment.currency`, `payment.latency_ms`) on `express_checkout_confirmed`. The LLD never states whether/how nested structures get flattened into columns vs. stored as `Tuple`/`Nested`/`JSON` types — this is exactly the "map raw events to schema" requirement from the problem statement, and it's the one piece of real complexity in the sample data. Currently unaddressed.
- **No dedup / data-quality handling.** `instrumentation_notes.md` explicitly documents `duplicate_id` and `is_back_filled` columns as "known texture (kept faithful to prod)," plus widespread `Nullable` columns and messy `os`/`device_type` values (`ios`, `android`, `web-user-b2c`, `Desktop` — inconsistent casing/taxonomy; some Android rows have `os = NULL`). None of this is addressed by the Instrumentation Engineer's schema design or by any Analyst-side normalization tool. Without it, funnel/segment queries will silently double-count or misbucket.
- **No idempotency strategy.** What happens if `run_ingestion.py` is invoked twice against the same spec folder (e.g., a rerun after a fix, or the 6th spec re-processed under time pressure)? `CREATE TABLE` will fail on the second run. Needs `CREATE TABLE IF NOT EXISTS` / `CREATE OR REPLACE` decision, stated explicitly.
- **No engine choice discussion.** `MergeTree` vs. `ReplacingMergeTree` (for the dedup problem above) vs. `AggregatingMergeTree` (for MV rollups) is never discussed — this is core to "schema quality."

### 3.2 Analytics Agent / Product Analyst

- **No statistical rigor specified.** Problem statement asks for "trends, anomalies, segment comparisons, correlations" and confidence scores. The design only says the Analyst writes `sequenceMatch`/`windowFunnel` SQL and "synthesizes outputs" — no method for anomaly detection, significance testing, or how a confidence score is actually computed (sample-size threshold? bootstrap CI? just an LLM self-rated number, which judges would rightly distrust?).
- **No explicit token-budget safeguard.** The problem statement gives a direct hint: *"an Analytics Agent that pulls raw rows into the LLM will burn your token budget fast."* `Tool_Analytics_Compute` returns "aggregated JSON" which is good, but the design never states a hard constraint (e.g., tool rejects/truncates any result set above N rows) preventing an agent from accidentally writing a `SELECT *` and blowing the budget.
- **No PM-audience output template.** The problem statement explicitly requires (for the unseen spec in particular) an insight summary "written for a product audience, not a database one." The design's `generate_insights_task` output is just "final Deliverable Insight formatted text" — no structure (headline finding → why → segment breakdown → confidence → recommended action).
- **Multi-cut requirement not enforced.** `base_context.md` §7 mandates cutting by "at least device, geo, and destination before concluding." Nothing in `tasks.py`/`agents.py` enforces this as a required step rather than an optional LLM choice.

### 3.3 Context Agent / Context Librarian — Critically Deficient

- **Read-only, not living.** The problem statement requires the Context Agent to "maintain and evolve," "auto-update... when new tables or columns are added," and "surface contradictions or gaps." The current `Context Librarian` only does JIT SQL *reads*. There is no task, tool, or trigger that writes new facts back into `chDB` after CUJ 1 creates a table — meaning by the design's own architecture, context is frozen at whatever `Tool_Init_chDB_Context()` loaded from `base_context.md` on day one.
- **No schema-metadata sync.** `Tool_Init_chDB_Context()` only ingests `base_context.md` (prose). It never ingests `data/ddl.sql` or the live ClickHouse `system.columns` for the 8 existing tables or any newly created tables. Concretely: without this, the Product Analyst agent has no reliable way to know what columns exist on a table it's about to query — it would have to guess or hallucinate column names. This is a functional gap, not just a nice-to-have.
- **A real, concrete contradiction exists in `base_context.md` that the design does nothing to catch.** §4 states: *"Conversion rate = completed purchases ÷ **sessions**."* Then, three paragraphs later: *"we treat **conversion as `purchase_completed` users ÷ users who started an application** (`application_started`)."* These are two different denominators for the same named metric ("conversion rate" vs. "funnel conversion") — and worse, **no raw table in `ddl.sql` has a session-grain field** (only `app_session_id` on the shared envelope, not a session table/count). This is precisely the kind of contradiction the problem statement warns exists ("the base context layer... is not perfect... treat it with suspicion") and that a real Context Agent should surface. The design has no contradiction-detection mechanism, and this specific example — a genuinely undefined "sessions" denominator — should be name-checked as evidence the agent works.
- **No versioned storage for the changelog requirement.** The visualization layer must show "context layer diff/changelog" (problem statement, Tracing/Viz section). `chDB` is chosen for context storage but the design gives no schema for storing *history* (e.g., an append-only `context_history(version, ts, entity, field, old_value, new_value, source_task_id)` table) — without that, there is nothing to diff.

### 3.4 Tracing and Visualization Layer

- **Visualization layer is completely missing.** Not a component, not a CUJ, not a tech choice. The problem statement requires a dashboard/lightweight UI/structured CLI showing: (a) schema changes over time, (b) agent insights with confidence scores, (c) context layer diff/changelog. None of the three exist in the current design.
- **Trace-to-deliverable linkage unspecified.** Langfuse is wired for tracing, but the design never states how a specific trace URL/ID gets attached to a specific deliverable artifact (e.g., the 6th-spec schema + insight bundle) so a judge can go from "here's the output" to "here's the exact trace that produced it" — which is the literal bar set by "No trace, no credit."
- **ClickStack** is offered in the problem statement as an optional system-level tracing layer ("if you want to go further") — the design doesn't mention considering or rejecting it; a one-line justification would close this out.

### 3.5 The Unseen 6th Spec — Unaddressed

This is called out by the problem statement as carrying "significant weight in shortlisting and beyond," yet the design doc contains **zero** mentions of it. Missing entirely:
- An operational runbook for the live Day-2 window: spec folder arrives → CLI invoked → HITL approval → trace captured → insight generated, all under time pressure, with no chance for pre-tuning.
- A stated SLA/turnaround target and what happens if the pipeline errors on a spec shape it hasn't seen (the design's 5 known specs all lack nested objects except #1; an unseen spec could have arbitrary nesting/types the Instrumentation Engineer has never handled — the "no heuristic" gap in §3.1 becomes acute here).
- The HITL gate in CUJ 1 requires a human to type "APPROVE" — allowed per the rules, but the design should explicitly state who/how this happens fast enough during the live window, since a stalled approval could blow the submission deadline. No fallback or timeout behavior is defined.
- Explicit statement that the sixth-spec artifacts (schema DDL, insight summary, Langfuse trace export) are captured as standalone submission evidence — not just left sitting in ClickHouse Cloud / Langfuse's UI.

---

## 4. What Must Be Added to `atlys_tech_design.md`

### 4.1 HLD Additions
1. **Context Agent, rescoped as read-write.** Rename/expand `Context Librarian` responsibilities to explicitly include: write-back after DDL execution, contradiction/gap surfacing, and versioned storage.
2. **Visualization Service** as a first-class component (own section, not folded into "Verification Plan"). State the tech choice (e.g., Streamlit reading from `chDB`/ClickHouse, or a rich-CLI/structured Markdown report per run) and what each of the 3 required views renders from.
3. **Unseen-spec operational path** as its own top-level HLD concern — not just "CUJ 1 runs again."

### 4.2 LLD Additions
1. **Schema design heuristic**, written down, not just "the LLM figures it out" — e.g.: ordering key = low-to-high cardinality columns that match the funnel/segment query patterns in `base_context.md` §7 (`destination`, `device_type`/`os`, `toDate(timestamp)`, then `user_id`); partitioning by `toYYYYMM(timestamp)`; TTL policy for raw event tables (e.g., 13 months, matching typical funnel reporting windows); `ReplacingMergeTree` keyed on `id` (or a version column) to resolve `duplicate_id`/`is_back_filled`.
2. **`Tool_Sync_Schema_Metadata()`** — new tool: after any DDL runs (existing 8 tables at init, or new tables from CUJ 1), reflect `system.columns`/`system.tables` into `chDB` so the Analyst always has ground-truth schema, not prose alone.
3. **`Tool_Context_Diff()` / `Tool_Context_Audit()`** — new tools on the Context Librarian: audit `chDB`'s business-context table for conflicting metric definitions (the "sessions" contradiction in §3.3 is a concrete test case), and append a diff row to a `context_history` table whenever context changes.
4. **Insight output schema** — define the actual structure of "Deliverable Insight" (headline / segment cuts / why-explanation citing context / confidence score + method / recommended action), not free text.
5. **Nested-event flattening rule** for the Instrumentation Engineer (e.g., dot-notation flattening of one level of nesting into typed columns, given `payment.*` in spec 1).
6. **Row-volume guardrail** in `Tool_Analytics_Compute` (reject/downsample any query attempting to return more than N rows to the LLM).

### 4.3 CUJ Additions
- **[NEW] CUJ 3 — Context Evolution & Auditing.** Trigger: CUJ 1's DDL is approved. Flow: Context Librarian syncs new schema metadata, checks it against existing context for contradictions, writes a changelog entry, flags anything unresolved for human review.
- **[NEW] CUJ 4 — The Unseen 6th Spec (Day 2 live run).** End-to-end runbook: spec drop → ingestion → HITL approval (with a stated turnaround target) → analytics → insight generation → trace export → artifact packaging for submission. This is the CUJ judges will scrutinize most; it should be the most detailed one in the document, not the missing one.
- **[NEW] CUJ 5 — Visualization / Review.** How a PM or judge opens the dashboard/CLI output and sees schema history, insights with confidence, and the context changelog.
- *(Optional but recommended)* **CUJ 6 — Failure/Rollback.** What happens when `Tool_Execute_DDL` fails half-way (Cloud succeeds, `chDB` mirror fails, or vice versa) — the doc currently assumes both always succeed together.

### 4.4 Technology Choices Needing Explicit Justification
- **chDB for context + history:** state the concrete schema (tables, not just "chunks") and how it satisfies the changelog requirement — judges are told to expect this question.
- **Visualization stack:** name it (Streamlit / rich CLI / static HTML report) and why, given the "out of scope: polished frontends" note — a lightweight choice is actually the *correct* answer here, but it must be stated, not omitted.
- **ClickHouse MCP server:** the problem statement flags this as a preconfigured starting point. The design uses hand-rolled `clickhouse-connect` tools instead — add one sentence on why (e.g., tighter control over DDL approval gating than MCP's generic tool surface allows).
- **`ReplacingMergeTree`/dedup strategy** vs. plain `MergeTree`, justified against the `duplicate_id`/`is_back_filled` texture in the real data.
- **Langfuse trace → artifact linkage mechanism**, explicitly.

---

## 5. Priority Fix List (before implementation starts)

| Priority | Item | Why |
|---|---|---|
| P0 | Add CUJ 4 (unseen spec runbook) | Highest-weighted, currently zero coverage |
| P0 | Make Context Librarian read-write (§3.3, §4.1-1, §4.2-2/3) | 2 of 5 criteria depend on this; currently architecturally impossible |
| P0 | Add Visualization component | Explicit deliverable, entirely missing |
| P1 | Schema heuristic + TTL + dedup strategy (§3.1, §4.2-1) | Directly judged as "schema quality" |
| P1 | Insight output template + confidence-score method (§3.2, §4.2-4) | Directly judged as "insight quality" |
| P1 | Trace-to-artifact linkage | Required for "no trace, no credit" |
| P2 | Nested-JSON flattening rule, row-volume guardrail, idempotent DDL, HITL timeout | Correctness/robustness under live-event pressure |

---

## 6. Conclusion

The architecture's core split (async HITL ingestion vs. synchronous read-only analyst) is sound and the "no CrewAI magic memory, explicit SQL context routing" constraint is a defensible engineering choice. But as written, the document would score poorly on 3 of 5 judged criteria and is silent on the criterion judges weight most heavily. The fixes above are not polish — they are the difference between a design doc that describes an agent loop and one that actually satisfies "Context Agent," "visualization layer," and "unseen spec" as literally scoped by the problem statement. Recommend addressing all P0 items before writing any implementation code.
