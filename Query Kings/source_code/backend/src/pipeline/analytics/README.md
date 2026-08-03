# Analytics Ask Harness

This folder owns the PM-facing analytics loop. It answers questions against the current ClickHouse warehouse and generated context memory. It is separate from the instrumentation agent: instrumentation builds/loads Silver tables and updates context; this harness uses those tables and context to answer arbitrary PM questions.

## Flow

```text
PM question
  -> 08a Query Understanding
  -> 08b PM Context Retrieval
  -> 08c Analysis Planner
  -> 08d Plan Critic
  -> 08e SQL Generator
  -> 08e2 Analytics Primitives
  -> 08f SQL Guardrail
  -> 09 Gold Query Executor
  -> 09b Result Evaluator
       -> repair once when SQL/results are weak
  -> 10 Insight Synthesizer
  -> 11 Evidence Critic
```

## Try These Questions

Run from `backend/`:

```bash
pnpm cli ask "Give me a PM summary of express checkout performance. What is working and what needs attention?"
```

```bash
pnpm cli ask "Where are users dropping off in the express checkout funnel?"
```

```bash
pnpm cli ask "Is express checkout completion worse on iOS than Android or web?"
```

```bash
pnpm cli ask "Which segment has the lowest success rate for group family applications?"
```

```bash
pnpm cli ask "Are there any data quality issues in the instant forex instrumentation?"
```

```bash
pnpm cli ask "What tables and events are available for abandoned checkout recovery, and what metrics can we calculate?"
```

Best first smoke test:

```bash
pnpm cli ask "Where are users dropping off in the express checkout funnel, and is the drop concentrated by device or country?"
```

The LLM is allowed to parse, plan, generate SQL drafts, and synthesize PM-facing text. Deterministic code retrieves context, blocks mutating SQL, executes ClickHouse queries, checks result quality, and removes unsupported final claims.

## Agentic vs Deterministic

The analytics harness is intentionally hybrid. The LLM is used where PM language is ambiguous and interpretation is needed. Deterministic code owns safety, execution, evidence checks, and traceability.

Agentic stages:

- `08a_query_understanding`: parses the PM question into intent, feature hints, metric hints, segments, time hints, and ambiguity notes.
- `08c_analysis_planner`: decides what analyses are needed, which tables/joins may matter, what queries should be run, and what evidence standard is required.
- `08e_sql_generator`: drafts read-only ClickHouse SQL from the analysis plan and retrieved context.
- `10_insight_synthesizer`: turns compact query results into a PM-facing answer with findings, caveats, and recommended actions.

Deterministic stages:

- `08b_pm_context_retrieval`: scores and retrieves generated context memory for the PM query.
- `08d_plan_critic`: checks that the plan is usable before SQL generation.
- `08e2_analytics_primitives`: adds broad reusable SQL primitives when context exposes the needed table/column shape.
- `08f_sql_guardrail`: blocks mutating SQL, strips formatting, checks known tables, and records warnings.
- `09_gold_query_executor`: executes approved ClickHouse queries and records every query.
- `09b_result_evaluator`: checks whether results are empty, weak, missing required evidence, or need repair.
- `11_evidence_critic`: removes unsupported final claims and adds caveats when evidence is weak.

The important trust boundary is:

```text
LLM drafts intent, plan, SQL, and prose
  -> deterministic code validates, executes, tracks, and constrains claims
```

## Tracking Contract

Every PM question produces three layers of tracking:

1. Langfuse trace
   - Root span: `schema-kings.analytics_ask`
   - Agentic generation spans:
     - `groq.analytics.query_intent`
     - `groq.analytics.analysis_plan`
     - `groq.analytics.sql_generator`
     - `groq.analytics.insight_synthesizer`
   - Stage spans for deterministic steps.

2. ClickHouse ops tables
   - `ops.pipeline_runs`: one row for the PM ask job lifecycle.
   - `ops.pipeline_stages`: one row per analytics stage with input/output JSON.
   - `ops.analytics_queries`: one row per SQL query with SQL text, purpose, guardrail warnings, status, row count, duration, and error.

3. Artifact files

   Each run writes artifacts under:

   ```text
   backend/artifacts/<job_id>/
   ```

   Important artifacts:
   - `08a_query_understanding/intent.json`
   - `08b_pm_context_retrieval/pm_context.json`
   - `08c_analysis_planner/analysis_plan.json`
   - `08d_plan_critic/plan_review.json`
   - `08e_sql_generator/sql_queries.json`
   - `08e2_analytics_primitives/primitive_queries.json`
   - `08f_sql_guardrail/sql_guardrail.json`
   - `09_gold_query_executor/query_results.json`
   - `09b_result_evaluator/result_evaluation.json`
   - `10_insight_synthesizer/answer.md`
   - `11_evidence_critic/final_answer.md`
   - `ask_summary.json`

This is the evidence trail judges should be able to inspect: what the system thought the PM asked, what context it used, what SQL it generated, which queries actually ran, what came back from ClickHouse, and how the final answer was constrained by evidence.

## Analytics Primitives

The harness is not limited to fixed agents, but it does include broad reusable primitives for the categories named in the problem statement. These are deterministic SQL templates generated only when the retrieved context exposes the required table and column shape.

Current primitives:

- **Event overview**: row count by event name.
- **Data quality**: row count, unique events, entity coverage, event id uniqueness, and time range.
- **Trend scan**: daily event trend by event name.
- **Anomaly scan**: simple daily-volume z-score over available days.
- **Funnel breakdown**: unique entities reaching each event, with success-event flag when context knows it.
- **Segment comparison**: entity volume and success rate by a segment column such as device, OS, country, destination, or citizenship.
- **Latency distribution**: p50/p90/p95 by event when latency-like columns exist.
- **Correlation scan**: Pearson correlation between two numeric columns when available.

These primitives do not replace dynamic SQL generation. The flow is:

```text
LLM planner/generator handles arbitrary PM intent
  + deterministic primitives add reliable common analytical cuts
  -> guardrails validate all SQL
  -> ClickHouse executes only approved queries
```

This gives coverage for trends, anomalies, segment comparisons, correlations, funnel stages, and quality checks without pretending every possible PM question can be pre-modeled.

## Why This Is Not Fixed To A Few Agents

The planner can create any set of query tasks needed for a PM question. The harness is not limited to a fixed funnel/segment/anomaly router. Common analyses still emerge naturally through the plan, but the control loop remains flexible for unseen questions.

## Context Retrieval

The existing context layer already stores generated feature, workflow, metric, column, join, contradiction, and schema quality memory. This folder adds PM-question retrieval over that memory. It is intentionally separate from `retrieveRelevantContextForSpec`, which is shaped for instrumentation prompts.

## Trust Boundaries

- Context is useful memory, not guaranteed truth.
- Generated SQL is a draft until guardrails and ClickHouse execution pass.
- Empty or weak results trigger repair once.
- The final answer is evidence-grounded; unsupported claims are downgraded or removed.

## Warehouse Tables Analytics Can Query

Analytics is not limited to `silver` / `gold` / `context`. The guardrail allowlist also includes the **8 base Atlys event tables** in the app database (`schema_kings` by default):

- Funnel: `destination_card_clicked`, `application_started`, `document_uploaded`, `purchase_completed`
- Supporting: `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`

Generated feature tables must be referenced as `silver.<feature>_events`.

SQL generation is grounded with:

1. Exact table/column catalog from PM context retrieval
2. Live `system.tables` allowlist (base + silver + gold + context)
3. Deterministic rewrite of common invented names (`express_checkout_logs` → `silver.express_checkout_events`)
4. Deterministic primitives (feature funnel, segment success, base funnel, feature↔purchase overlap)

If context memory has no matching feature, retrieval emits a loud WARNING and falls back to base funnel tables instead of inventing schema.

## Cross-Table Reasoning

Join memory now stores explicit edges from each Silver feature table to each base event table on `user_id` / `application_id`. The planner injects those joins for uplift/baseline questions. Primitives include:

- base funnel stage volumes
- base funnel conversion by `device_type` (for K1-style iOS checks)
- feature success users ∩ `purchase_completed` overlap

## Confidence Surface

Final answers (CLI + `final_answer.md`) include an **Evidence (claim → query → confidence)** section. Confidence is not only a viz concern — judges can read it from artifacts without a UI.

## Model routing (budget)

Uses env roles via `backend/src/pipeline/models.ts`:

| Stage                             | Role                | Default env                                                      |
| --------------------------------- | ------------------- | ---------------------------------------------------------------- |
| Intent parse                      | `intent` / fast     | `GROQ_FAST_MODEL` → `GROQ_CRITIC_MODEL` → `llama-3.1-8b-instant` |
| Analysis plan                     | `plan` / fast       | same cheap model                                                 |
| SQL generator                     | `sql` / default     | `GROQ_MODEL` → `openai/gpt-oss-20b`                              |
| Insight prose                     | `insight` / fast    | cheap model (numbers-first backs it up)                          |
| Schema design / critic / revision | `schema` / `critic` | `GROQ_SCHEMA_MODEL` / `GROQ_CRITIC_MODEL`                        |

Your current setup is a good cost balance: 8b for most JSON stages, 20b only where SQL quality matters.

## Gold-first primitives

When Gold targets exist for a feature (`*_daily_event_counts`, `*_daily_conversion`, `*_segment_success`, `*_latency_by_event`), primitives query those first and skip redundant Silver scans for the same cut.

## Strict Mode (no invented answers)

Analytics prefers **no reply over a wrong reply**:

- LLM stages must return valid structured output when used for planning/SQL/prose.
- If the LLM fails **and** there are no warehouse rows: return a graceful unavailable message (`please try later`) — never fabricate metrics.
- If ClickHouse returned real rows: a **numbers-first** deterministic scaffold summarizes those rows even if insight prose is weak.
- Missing planned SQL is **omitted**, not invented; deterministic primitives carry the reliable backbone.
- `min_rows` is clamped to **1 non-empty result set** (aggregates are not required to return 1000 JSON rows).
- Unknown features are refused: list instrumented features, do not attribute another feature’s metrics.
- Junk `table_hints` like `user_sessions` / `checkout_events` are stripped before planning.
