# Report / Visualization Layer

This folder owns the **judge-facing visualization layer** for the problem statement: schema over time, insights with confidence, and context changelog — plus Langfuse deep-links. It does **not** re-run agents to invent data. It reads pipeline artifacts (and optionally serves a tiny UI that calls the same `ask` path as the CLI).

Langfuse already covers agent/LLM tracing. This layer is presentation + demo UX.

---

## What the problem statement wants

A visualization layer (dashboard, lightweight UI, or structured output) showing:

1. **Schema changes over time**
2. **Agent-generated insights with confidence scores**
3. **Context layer diff / changelog**

Tracing stays in Langfuse; this module links out with `langfuse_trace_id`.

---

## Flow

```text
backend/artifacts/<job_id>/...
        │
        ▼
  assemble.ts     → PipelineReport (overview | ask | run)
        │
        ▼
  renderHtml.ts   → HTML string
        │
        ▼
  generateReport.ts → frontend/dist/report.html
                    → frontend/dist/report-data.json

Optional:
  server.ts  →  GET /  (report)
             →  POST /api/ask  (runAnalyticsAsk → focused report)
```

```text
pnpm cli report [job_id]   # write HTML from artifacts
pnpm cli ask "…"           # analytics, then auto-report for that job
pnpm cli serve             # http://127.0.0.1:8787 — ask box + report
```

---

## Modes

| Mode       | When                                              | Page content                                                             |
| ---------- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| `overview` | `pnpm cli report` (no job)                        | All instrumented features, context summary, 3 recent clean asks          |
| `ask`      | `pnpm cli report <ask_job_id>` or after serve ask | One PM question → answer, findings, actions, evidence, caveats, Langfuse |
| `run`      | `pnpm cli report <run_job_id>`                    | One instrumentation job → schema + context diff for that feature         |

Job ids accept a **full folder name** or a **unique prefix** (e.g. `20260801T212355`).

Junk / adversarial ask folders (`asdf`, `drop table`, …) are filtered out of the overview “recent insights” list.

---

## Module map

| File                | Role                                                                     |
| ------------------- | ------------------------------------------------------------------------ |
| `types.ts`          | `PipelineReport`, `AskCard`, `FeatureCard`, evidence types               |
| `assemble.ts`       | Scan `backend/artifacts/`, build overview or focused report              |
| `langfuseUrl.ts`    | Trace URL from `LANGFUSE_BASE_URL` + `LANGFUSE_PROJECT_ID` (or template) |
| `renderHtml.ts`     | Tailwind CDN HTML, ask box, loading UI, sections                         |
| `generateReport.ts` | Write `frontend/dist/report.html` + `report-data.json`                   |
| `server.ts`         | Tiny HTTP server for demo ask + report                                   |
| `index.ts`          | Public exports                                                           |

Presentation output lives under `frontend/dist/` (gitignored). See also [`frontend/README.md`](../../../../frontend/README.md).

---

## Artifact sources

| Report piece                  | Typical source                                       |
| ----------------------------- | ---------------------------------------------------- |
| Insight + findings + evidence | `11_evidence_critic/final_answer.json`               |
| Question / trace id           | `ask_summary.json`                                   |
| Schema SQL / plan             | `04_schema_generator/schema.sql`, `schema_plan.json` |
| Schema over time              | All `run_summary.json` jobs under artifacts          |
| Context changelog             | `07_context_agent/context_diff.md`                   |
| Contradictions                | `updated_context.json` / ask `pm_context.json`       |
| Langfuse                      | `langfuse_trace_id` in summaries                     |

Read-only. No ClickHouse required to **render** a report from existing artifacts.  
`POST /api/ask` does call analytics (and thus ClickHouse) — same as `cli ask`.

---

## Langfuse links

Default (with project id set):

```text
{LANGFUSE_BASE_URL}/project/{LANGFUSE_PROJECT_ID}/traces/{trace_id}
```

Optional override:

```env
LANGFUSE_TRACE_URL_TEMPLATE=https://jp.cloud.langfuse.com/project/YOUR_ID/traces/{trace_id}
```

---

## Serve / ask UX

`pnpm cli serve` (default port `8787`, override with `--port` or `REPORT_PORT`):

- `GET /` or `/report.html` — regenerates and serves the report (`?job=` for focus)
- `POST /api/ask` `{ "question": "…" }` — runs `runAnalyticsAsk`, writes focused report, returns `report_url`
- Ask box on the page shows a **loading state** (spinner, rotating stages, elapsed timer) while the agent runs
- Opening `report.html` as `file://` can view content; the ask box requires `cli serve`

---

## Design principles

1. **Artifacts first** — UI never invents metrics; it displays what the pipeline already wrote.
2. **Judge-friendly** — overview tells the full story; focus pages are for one demo ask/run.
3. **CLI and UI share one brain** — serve ask = `cli ask`.
4. **No large API surface** — one optional POST for demo; no auth, no multi-tenant app.
5. **Keep analytics in `analytics/`** — this folder is assemble + render + thin server only.

---

## Trust boundary

```text
Pipeline / analytics write artifacts + Langfuse
  → report module only reads and presents
  → serve may trigger analytics, then presents that job’s artifacts
```
