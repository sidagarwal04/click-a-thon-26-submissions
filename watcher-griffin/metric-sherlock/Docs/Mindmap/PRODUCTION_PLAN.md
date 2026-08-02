# Production Plan — Automated Root-Cause Analyst

Canonical phase-wise build order for turning the loaded ClickHouse star schema into the judged deliverable: detect → drill down → evidence → narrate → trace. See `PROJECT_CONTEXT.md`, `SYSTEM_ARCHITECTURE.md`, `INVESTIGATION_ENGINE.md`, `CLICKHOUSE_DESIGN.md` for the condensed architecture this expands on, and `../../PROGRESS.md` (repo root) for live status.

> **Historical document.** Statuses and counts below were accurate when written; the build has
> since grown past them (full-coverage monitoring, the backtest, the dataset registry and the
> unseen `unseen_data` database — see `PROGRESS.md`). Test counts quoted per phase are the
> counts at that phase's completion, not today's.

Orchestration style: a **fixed deterministic pipeline**, not a free-form LLM tool-calling loop. Every step is plain Python + SQL; the LLM only narrates the final evidence JSON. **Rollup tables (`hourly_*`) are the first and default source** for every query — raw `ad_events` is only queried when a rollup can't answer the question (e.g. a 2D drill-down like device × region), and every such fallback query is captured verbatim in the evidence trace.

**Surviving the unseen dataset is the top priority**, ahead of feature breadth — every phase is designed so it still works when the data volume, date range, or dimension cardinalities are not today's. That is a correctness requirement, not an ambition: the brief states that a fresh slice of the same universe with new planted anomalies is released in the final hours and that submissions are judged on what the system produced for it. Code that assumes the Jun 1–Jul 5 window, the 9M row count, or the dimension values present in the sample would simply be wrong against that input.

Read the principles below in that light. They are here because an unseen input demands them, **not** because this is aiming at production traffic — the brief puts production deployment explicitly out of scope, and nothing in this build should be justified by throughput it will never see. Where a scalability property has no unseen-dataset justification, it is not a goal. See `../DESIGN_RATIONALE.md`, which measures the ones that were challenged rather than asserting them.

---

## Production & scalability principles (cross-cutting — apply in every phase)

1. **Data-volume agnostic, not hardcoded to this sample.** No code assumes the Jun 1–Jul 5 2026 date range, today's dimension cardinalities, or today's 9M row count. Baseline windows, dimension lists, and thresholds are config, not literals — this is also what "build for the unseen incident" requires functionally.
2. **The rollup layer is what makes this scale, not raw-table cleverness.** Every rollup stays a small fraction of raw-row count regardless of how large `ad_events` grows. Any new slicing dimension gets its own narrow `hourly_by_*` rollup, never a wider composite-key rollup whose cardinality could approach the fact table's.
3. **Bounded, resilient ClickHouse access.** Every query goes through one client wrapper with a query timeout (`max_execution_time`), a result-size cap, and retry-with-backoff on transient errors.
4. **Concurrency where independent, not serial by default.** Steps that query multiple independent rollups run concurrently, not as N sequential round-trips — this is what keeps "diagnosed in seconds" true as the dimension list grows.
5. **Stateless, horizontally replicable service.** The API holds no in-process state between requests (evidence/trace state lives in ClickHouse + Langfuse, not in memory).
6. **Config and secrets externalized.** One `config.py` (pydantic-settings) reading env vars (ClickHouse Cloud endpoint, Langfuse keys, LLM provider key, baseline-window sizes, anomaly thresholds) — nothing hardcoded, nothing new checked into git.
7. **Fails safe, never fails silent-wrong.** If Langfuse or the LLM provider is unreachable, the API still returns the deterministic evidence JSON with narration replaced by an explicit "narration unavailable" flag — never a guessed or templated number.
8. **Tested, not just demoed.** Unit tests for the decomposition/contribution math and one integration test that runs the full pipeline against a known window and asserts on exact numbers.
9. **Containerized and one-command runnable.** A `Dockerfile` + `docker-compose.yml` so the exact tested artifact is what runs for the unseen incident.

---

## Phase 0 — Finish the ClickHouse foundation (~30–45 min)

`schema.sql` + `load.sql` are already applied live (`ad_events_main`: 9M-row `ad_events`, 2K `apps`, 500 `advertisers`, 5K `geo_device`). `dictionaries.sql`/`rollups.sql` are written but not yet applied. Since `load.sql` already ran, the rollup MVs **will not backfill the existing 9M rows** (MVs only fire on rows inserted after creation) — a one-time manual backfill is required.

**Status: done.** `scripts/apply_and_backfill.py` runs all of the below in one idempotent command (`.venv/Scripts/python.exe scripts/apply_and_backfill.py all`) — it exists because the `mcp__clickhouse` MCP connection is read-only, so DDL/DML goes through a direct `clickhouse-connect` client instead of `clickhouse-client --queries-file`. Already run once; safe to re-run against the unseen-incident dataset (skips anything already created/populated).

1. Run `clickhouse/dictionaries.sql` against `ad_events_main`.
2. Run `clickhouse/rollups.sql` (creates the 12 `hourly_*` tables + MVs).
3. For each `hourly_*` table, run a one-time `INSERT INTO hourly_x SELECT <same body as the MV's SELECT> FROM ad_events GROUP BY ...` to backfill history, reusing the exact SELECT bodies already in rollups.sql.
4. Sanity check: `SELECT count(), sum(requests) FROM hourly_overall` reconciles against `ad_events` — verified: 9,000,000 requests / 7,027,910 fills / 17,020.364187 revenue match exactly.
5. Set query-level resource limits (`max_execution_time`, `max_memory_usage`) as connection defaults so a runaway raw-table fallback can't stall the service for other requests — still to do inside `engine/ch_client.py` in Phase 1, not part of the one-off apply script.

## Phase 1 — Investigation Engine core (deterministic pipeline) (~3–4 hrs)

**Status: done, since reapproached with LangGraph.** All modules below implemented under `engine/`; orchestration now runs as a LangGraph `StateGraph` (`engine/graph.py`) with genuine recursive drill-down (a node that loops back on itself up to `max_drilldown_depth`) instead of a hardcoded two-level special case — see `INVESTIGATION_ENGINE.md`'s "Orchestration" section for why. 15 `pytest` tests pass, including an integration test against live ClickHouse with hand-verified numbers and pure-logic tests for the graph's conditional edges (see `PROGRESS.md`).

Implements `INVESTIGATION_ENGINE.md`'s 7 steps as one Python package, `engine/` (only the narrator step touches an LLM):

| Step | Module | Role |
|---|---|---|
| 1. Validate baseline | `engine/baseline.py` | Incident window vs like-for-like baseline (same weekday, trailing N weeks, N from config) |
| 2. Decompose metric | `engine/decompose.py` | Revenue ≈ Requests × Fill rate × eCPM/1000 against `hourly_overall`, isolates which factor moved |
| 3. Rank dimensions | `engine/rank.py` | Queries relevant `hourly_by_*` rollups **concurrently**, ranks dimension values by contribution/share-of-shift |
| 4. Recursive drill-down | `engine/drilldown.py` | Re-ranks within the top segment; 2D slices not covered by any rollup fall back to raw `ad_events` (bloom-filter/projection-backed), logged verbatim |
| 5. Rule out alternatives | `engine/rule_out.py` | Records dimensions/factors that did NOT explain the deviation, with actual numbers; seasonality check always runs |
| 6. Generate evidence | `engine/evidence.py` | Pydantic `EvidenceBundle` — metrics, every SQL query + result, ranked segments, ruled-out list. The only thing that reaches the LLM. |
| 7. Narrate findings | `engine/narrator.py` | LLM call, restates only numbers already in the evidence JSON; degrades to "narration unavailable" rather than fabricating on failure |

Plus:
- `engine/config.py` — pydantic-settings: env vars, baseline-window size, anomaly thresholds, dimension registry (adding a rollup later shouldn't require touching engine logic).
- `engine/ch_client.py` — query timeout + retry/backoff wrapper; logs every query (text, params, row count, latency) into the trace list that becomes the evidence bundle.
- `engine/pipeline.py` — `run_investigation(metric, window)`, single entrypoint, stateless (safe under concurrent API workers).
- `tests/test_decompose.py`, `tests/test_rank.py` — pure-function unit tests for the contribution math.
- `tests/test_pipeline_integration.py` — full pipeline run against one known window, asserts exact numbers.

Contribution math: share-of-deviation, e.g. `(segment_metric_now - segment_metric_baseline) / (overall_metric_now - overall_metric_baseline)`, computed in Python — never left to the LLM.

## Phase 2 — Langfuse integration (traceability requirement) (~1–1.5 hrs)

**Status: done** (`engine/tracing.py`). No-ops safely without keys (verified); not yet exercised against a real Langfuse project.

- One parent Langfuse trace per `run_investigation()` call.
- Each `ch_client.py` query becomes a child **span** named after the step (`baseline_check`, `rank:hourly_by_region`, `drilldown_raw_fallback`, `rule_out:seasonality`), with SQL text + result summary as metadata.
- The `narrator.py` LLM call becomes a **generation** (input = evidence JSON, output = narration, model, latency, token cost).
- Ruled-out items get their own explicitly-named spans/events.
- Langfuse calls are fire-and-forget/async; if unreachable, the investigation still completes and returns evidence.

## Phase 3 — API + minimal demo surface (~1.5 hrs)

**Status: done and verified live.** `./scripts/deploy.sh` (or `scripts/deploy.ps1`) builds and runs the whole stack in one command; demo is at `http://127.0.0.1:8088` (moved off 8000 -- see `PROGRESS.md` gotchas).

- FastAPI service (multi-worker uvicorn/gunicorn, stateless): `POST /investigate {metric, window}` → `{evidence, narration, langfuse_trace_url}`. Pydantic request/response models. `GET /healthz`.
- Minimal demo UI (single HTML page or Streamlit): metric tree lights up green/amber/red, click a red node → narration + evidence table. Functional only — polished frontends are explicitly out of scope.
- `Dockerfile` + `docker-compose.yml` so the tested artifact is exactly what runs live.
- Optional stretch: follow-up Q&A via LibreChat against the same evidence JSON.

## Phase 4 — Detection loop (~1 hr)

**Status: done** (`engine/scanner.py`, `python -m engine.scanner --once|--interval`). Tested against the sample data via `--as-of`: correctly flagged a fill_rate deviation (z=-20.3) on a window where revenue itself looked normal, and auto-triggered the full investigation. Note: an earlier version of this paragraph excused high-magnitude z-scores on low-variance ratio metrics as "expected, not a bug". That claim was later **retracted**: it was a divide-by-near-zero (a nearly-flat trailing history yields a MAD near zero), fixed with the `min_relative_spread` floor in `engine/bands.py` and measured in the backtest — see `PROGRESS.md` gotcha 39 and `../DESIGN_RATIONALE.md` §5.

A scanner (separate scheduled process, decoupled from the request-serving API) runs `BaselineCheck` across `hourly_overall`/key sub-metrics on an interval, auto-flagging deviations and kicking off `run_investigation()` — the actual "Detect" requirement.

## Phase 5 — Unseen-incident rehearsal + hardening (final hours)

**Status: done.**

- Concurrent-load check: 8 parallel `/investigate` calls found a real concurrency bug -- `engine/ch_client.py`'s `get_client()` was a process-wide singleton, and concurrent API requests (each served on its own thread) sharing one `clickhouse_connect` client crashed with "concurrent queries within the same session." Fixed by making `get_client()` return one client per thread (`threading.local()`, lazily created, cached per thread) instead of one shared instance. Re-ran the same 8-concurrent-request test after the fix: all 8 returned 200, and latency did not degrade (max concurrent latency was actually *lower* than a cold single request, thanks to warmed connections/caches). Full `pytest` suite re-confirmed green after the fix.
- Synthetic-anomaly injection into live `ad_events` was deliberately **not done** -- it would corrupt the dataset that Phase 0 already reconciled exactly against the raw source, on a shared ClickHouse Cloud resource. Sensible-on-invented-deviations coverage instead comes from `tests/test_rank.py`/`test_decompose.py`'s synthetic-input unit tests (fabricated segment/factor deviations, not live data), plus the real fill_rate anomaly the Phase 4 scanner caught in the sample data (see below) as a live demonstration that detection isn't hardcoded to one known planted case.
- Rehearsed the exact one-command re-run: `./scripts/deploy.sh` (or `scripts/deploy.ps1`) builds + starts the whole stack and waits for `/healthz`; confirmed `/investigate` returns hand-verified numbers end to end through the container. This is the same command to run the moment the unseen dataset drops -- "no trace, no credit" is a hard scoring rule.

## Phase 6 — Claude Code build tooling: agents + rules

- `.claude/agents/clickhouse-query-writer.md` — rollup-first/raw-fallback SQL, always surfaces exact query text, bounded resource limits.
- `.claude/agents/investigation-engine-builder.md` — implements `engine/*.py` against this spec, one module at a time, always through `ch_client.py`, with a unit test per new pure-function module.
- `.claude/agents/narrator-prompt-engineer.md` — owns `narrator.py`'s prompt + Langfuse generation logging; owns the "never compute, only restate given numbers" and "degrade, don't fabricate" guardrails.
- `CLAUDE.md` — `## Guardrails` and `## Production & scalability principles` sections so both are enforced automatically in every future session.

---

## Verification (end-to-end)

1. `SELECT count() FROM hourly_overall` etc. confirms Phase 0 backfill worked.
2. `run_investigation()` against a known planted-anomaly window: evidence JSON numbers match hand-run ClickHouse queries (spot-check 2–3 numbers per run).
3. Open the resulting Langfuse trace: every step (baseline → decompose → rank → drilldown → rule-out → evidence → narration) appears as a labeled span/generation in order.
4. `POST /investigate` via `docker compose up`: demo UI renders narration + evidence with no manual steps.
5. `pytest` green; concurrent-load check shows latency doesn't degrade linearly with concurrent requests.
6. Synthetic-anomaly injection: pipeline still localizes correctly and rules out untouched dimensions.
