# Coding Standards — Jalagaara Gang

Hackathon rules: **fast, but not sloppy where it counts.** The parts judges inspect (the numbers, the SQL, the trace) get discipline. Everything else gets pragmatism. This doc is written to be handed to your AI agent as well as read by you.

## The prime directive

> **No number reaches the user unless a SQL query produced it and that query is in `queries[]` of the Evidence Bundle.**

Every rule below serves this. If you're ever unsure, optimize for *a judge being able to reproduce our number*.

## Golden rules for AI agents (paste into your agent when relevant)

1. **The LLM narrates; it never calculates.** Do not write code that asks the model to compute, estimate, sum, or compare metrics. The model receives finished numbers and writes sentences.
2. **Analysis lives in ClickHouse SQL**, not in Python loops over rows. If you're pulling raw events into pandas to aggregate, stop — write the aggregation as SQL. Pandas is allowed only for baseline stats on already-aggregated series.
3. **Emit the SQL alongside the result.** Any function that computes a number returns *both* the value and the SQL string that produced it, so it can land in `queries[]`.
4. **Match the glossary formulas exactly.** Ratios are `sum(x)/sum(y)` over the group — never an average of per-row ratios. Copy the formulas from [`InMobi/metrics_glossary.md`](../InMobi/metrics_glossary.md).
5. **Never hardcode an answer.** No segment names, dates, or thresholds tuned to a specific planted anomaly. The unseen incident will punish it.
6. **Verify before claiming done.** Run the code, capture the output, paste it. See "Definition of Done."
7. **No magic strings inside the code - keep everything config json file driven**
8. **Don't waste space when writing code or add unwanted comments. Only comment on key areas for the devs to note.**

## Python

- **Python 3.11+**, `uv` for env + deps. `ruff` for lint+format (one tool, zero config bikeshedding). `ruff format` before commit.
- **Type hints on all public functions.** `pydantic` models for anything crossing a boundary (API, Evidence Bundle). Generate the bundle model from [`contracts/evidence_bundle.schema.json`](../contracts/evidence_bundle.schema.json) or keep them in lockstep by hand.
- **No bare `except`.** Catch specific errors. A failed ClickHouse query should surface, not be swallowed.
- **SQL lives in `.sql` files or clearly-named string constants**, not scattered f-strings. Parameterize inputs (windows, filters) — never string-concatenate user/segment values into SQL. ClickHouse supports parameterized queries; use them.
- **Functions do one thing.** A drill-down step, a baseline calc, a narration call — each is its own testable function.
- Structure:
  ```
  backend/
    data/        # lane A: schema.sql, load scripts, query helpers
    rca/         # lane B: detection.py, decomposition.py, drilldown.py, bundle.py
    narrator/    # lane C: narrate.py, guardrail.py, tracing.py
    api/         # lane C: main.py (fastapi)
    tests/
  ```

## SQL / ClickHouse

- **Read against `events_full`** (denormalized fact+dims) so drill-downs are single-table `GROUP BY` — no repeated joins in the recursion.
- **Ratio metrics = sum/sum.** Bake this into shared SQL snippets so no one reinvents fill rate.
- **Baselines are like-for-like.** Same weekday + hour-of-day over trailing weeks, robust (median/MAD). A `toDayOfWeek()` / `toHour()` bucketed comparison — never `avg()` over the whole history.
- **Every query is named and logged.** Give it an id (`q_03`), log the exact SQL + params. That string goes into the bundle *and* the Langfuse span. This is non-negotiable — it's the traceability score.
- Prefer readable SQL with CTEs over clever one-liners. A judge will read it.
- Keep result sets small — aggregate in ClickHouse, return scalars/small tables. Never `SELECT *` 9M rows into the app.

## TypeScript / React (Lane D)

- **Vite + React + TS.** `pnpm`. `eslint` + `prettier`, defaults.
- Build against **`fixtures/sample_bundle.json`** first; wire the live API last. You should never be blocked on the backend.
- Components are dumb renderers of the Evidence Bundle. No business logic, no metric math in the frontend — it displays what the bundle says.
- Keep it lean. Metric tree, diagnosis card, ruled-out card, trace link, chat box. Resist scope creep — judges reward the investigation loop, not the chrome.

## Langfuse / tracing

- One **trace per investigation** (`investigation_id`). One **span per SQL query** (input = SQL+params, output = result_summary). One **generation span** for the narration (input = bundle, output = prose).
- Put the `trace_url` back into the bundle. The dashboard links to it. That link is what a judge clicks.

## Git

- Branch per lane. PRs small and frequent. `main` always runs.
- Commit messages: imperative, scoped — `data: add hourly rollup MV`, `rca: log-additive factor decomposition`.
- `.env` gitignored; `.env.example` committed. **Zero secrets in history** — the repo is public.
- Never `git push --force` shared branches. Never skip hooks.

## Definition of Done (per task)

A task is done when **all** are true:
- [ ] It runs. You executed it and saw the expected output — pasted in the PR/standup.
- [ ] Numbers (if any) come from logged SQL that's in `queries[]`.
- [ ] It conforms to the Evidence Bundle schema (validate against the JSON schema).
- [ ] It doesn't hardcode anything incident-specific.
- [ ] Someone else can run it from a clean checkout (deps in lockfile, env in `.env.example`).

"It should work" / "the agent says it's done" is **not** done. Evidence before assertion — every time.

## Anti-patterns (instant PR rejection)

- LLM doing arithmetic on data
- A number in the diagnosis with no matching query id.
- Flat-average baseline that alarms on every weekend.
- Hardcoded `WHERE country = 'IN'` because that's where the known anomaly is.
- Pulling raw events into Python to aggregate.