# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A pnpm/Turborepo monorepo building the "InMobi Automated Root-Cause Analyst" — see [`PLAN.md`](PLAN.md) for the full design. The system watches ad-tech metrics (revenue, fill rate, eCPM, CTR, requests) in ClickHouse, detects when one deviates from its seasonal baseline, and (eventually) auto-investigates *why* and narrates a diagnosis. Three deliberately separate stages, each with its own trust level:

1. **Detection** (reactive/scheduled, deterministic, no LLM) — `apps/detection-service`. Built.
2. **Investigation** (agentic, per-anomaly, tool-calling LLM loop over ClickHouse) — not yet built.
3. **Remediation** (advisory, lowest-trust, never mixed into the evidence-backed diagnosis) — not yet built.

Nothing in detection or investigation may be tuned to the specific planted anomalies visible during development — thresholds must stay statistical (z-score / seasonal baseline), because the system is scored against an unseen incident released separately. See `PLAN.md` for the reasoning behind the stage split and the current open questions.

## Repo layout

- `apps/detection-service` — **Stage 1, built.** Standalone Node deployment (a chain of ClickHouse materialized views, plus a small persistent process for what's genuinely schedule-based — see below), *not* part of `sentinel-agent` — it's headless, no LLM. See its own [README](apps/detection-service/README.md) for the full method-by-method rationale.
- `apps/sentinel-agent` — an [eve](https://eve.dev) framework app, currently just scaffold (default instructions, Slack + eve channels wired, no tools/schedules/subagents yet). Intended home for Stage 2/3 per `PLAN.md`, not implemented.
- `apps/web`, `apps/docs` — unmodified Turborepo starter Next.js apps (from `create-turbo`). Not yet part of the InMobi project's functionality.
- `packages/ui`, `packages/eslint-config`, `packages/typescript-config` — shared config/component packages from the Turborepo starter.

## Commands

Root (via Turborepo, runs across all workspaces):
```
pnpm build          # turbo run build
pnpm dev             # turbo run dev (persistent, uncached)
pnpm lint            # turbo run lint
pnpm check-types      # turbo run check-types
pnpm format          # prettier --write "**/*.{ts,tsx,md}"
```
Scope any of these to one workspace with `--filter`, e.g. `turbo run check-types --filter=detection-service`.

`apps/detection-service` (no `build`/`lint` script — a plain Node app, not Next.js):
```
cd apps/detection-service
npm run setup:local     # one-time: ClickHouse schema, detection_config seed, sql/mv/ materialized-view chain
npm run recompute:local # forces the whole refreshable MV chain to run now instead of waiting for its schedule
npm run sweep:local     # prints recent anomalies + current incident spans (there's no sweep to trigger anymore — see sql/mv/README.md)
npm run incidents:local # prints current incident spans only
npm start                 # runs the persistent process: just the 10-min incident/webhook poll now
npm run check-types
```
These need `CLICKHOUSE_URL` / `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` in `apps/detection-service/.env.local` (gitignored, not committed — ask the user for these rather than inventing them).

There is no test suite anywhere in this repo yet.

## Architecture: `apps/detection-service`

No LLM, "boring and reproducible" by design (`PLAN.md`'s explicit instruction for Stage 1). Two execution models, deliberately — see `sql/mv/README.md` for the full reasoning, including a real production bug that drove the split:

- **Reactive** — only the two single-hop rollups fire directly on `INSERT` into `inmobi.ad_events`: `sql/mv/01` (→ `metrics_hourly`) and `sql/mv/07` (→ `segment_metrics_hourly`). Proven reliable in production even under a large bulk load.
- **Refreshable** — everything cascaded from the rollups reschedules itself inside ClickHouse (`REFRESH EVERY ...`, chained via `DEPENDS ON`) and recomputes full history every cycle rather than reacting to inserts: `sql/mv/02` (seasonal z-residual → `metric_zr_hourly`), `sql/mv/03` (consolidated `trend_seasonal`+`proportion`+`day_level` → `anomalies`, `DEPENDS ON` (02)), `sql/mv/06` (daily noise baseline, `REFRESH EVERY 1 DAY`), `sql/mv/08` (consolidated segment `trend_seasonal`+`proportion` → `segment_anomalies`), `sql/mv/12` (canonical incidents, `anomalies` → `incidents`, `DEPENDS ON` (03)). A **cascaded** reactive MV (sourced from another MV's target table, not `ad_events` directly) was found empirically to silently stop firing on a large bulk INSERT — the rollup MVs kept working (single hop), but everything downstream of them stalled with no error. Refreshable sidesteps this by not depending on triggering at all.
- `lib/incremental/scheduler.ts` (`node-cron`, kept alive by `index.ts`) does exactly one thing now: a 10-minute poll that reads `inmobi.incidents` and fires `DETECTION_WEBHOOK_URL` on a state change (new incident opened / resolved). No separate incident store — dedup is process-local in-memory state (`lib/incremental/incidents.ts`), not Postgres. Detection itself has no app-level scheduled component at all — it's either reactive or ClickHouse's own refresh scheduler.
- `lib/clickhouse.ts` — thin wrapper around the official `@clickhouse/client` SDK, used by setup and the scheduled poll.
- **`cusum`, `ewma_fast`/`ewma_slow`, `basic`, and `forecast_regression` have all been removed from the codebase entirely** — no config rows, no state tables, no SQL files. `cusum`/`ewma` were dropped for the old reactive design's sake (a sequential recurrence / an unvalidatable variance estimate); `basic` never correlated with known incidents; `forecast_regression` (a `stochasticLinearRegressionState` experiment) was dropped as a direction — linear regression is no longer part of this project's approach. Active global ensemble: `trend_seasonal` + `proportion` + `day_level`. Active segment ensemble: `trend_seasonal` + `proportion` only. `detection_config` also has `incident_enabled` (separate from `enabled`) — CTR/render_rate are detected and kept as evidence but excluded from opening a paged incident (see `sql/01_detection_config_seed.sql`'s comment).
- `anomalies`/`segment_anomalies`/`metric_zr_hourly` are **plain `MergeTree`, not `ReplacingMergeTree`** — each has exactly one writer (its refreshable MV), which fully replaces the table's content every cycle, so there's nothing to dedupe. **Never query any of these three (or `incidents`) with `FINAL`** — ClickHouse Cloud's `SharedMergeTree` rejects `FINAL` outright on a non-Replacing table (`ILLEGAL_FINAL`), it does not silently no-op. `anomalies` still functions as an audit trail, just a continuously recomputed one: it always reflects what qualifies under the *current* `detection_config`, not whatever config was active when an hour was first scored.
- If a bulk-loaded date range looks incomplete downstream, don't assume the reactive rollups are broken — check whether the refreshable MVs have simply not run yet. `npm run recompute:local` forces the whole refreshable chain to run immediately in dependency order instead of waiting for its schedule.

**To add a new metric or query:** if it's a ratio derivable from existing `metrics_hourly`/`segment_metrics_hourly` columns, it's a same-shape line added to the `UNION ALL` blocks in the relevant `sql/mv/*.sql` file(s), plus a few threshold rows in `sql/01_detection_config_seed.sql` — no TypeScript changes, but changing an MV's query means dropping and recreating it (`CREATE OR REPLACE` doesn't apply to MVs the same way; see `sql/mv/README.md`). A wholly new detection *method* has to live inside the existing consolidated MV (`sql/mv/03` or `sql/mv/08`) as another `UNION ALL` branch, since `anomalies`/`segment_anomalies` can only have one writer under the refreshable-REPLACE design — see `sql/mv/README.md`. A metric needing a raw signal not yet in `ad_events` is out of this service's scope (upstream data pipeline).

**Ratio-metric rule, load-bearing everywhere in `sql/`:** fill rate, render rate, CTR, eCPM, RPR must always be computed as `sum / sum` over a group, never as an average of per-row or per-day ratios — getting this wrong silently corrupts every rollup. This mirrors the metrics glossary the source dataset ships with.

## Architecture: `apps/sentinel-agent`

Standard [eve](https://eve.dev) project layout — read `node_modules/eve/docs/README.md` before adding capabilities. `agent/agent.ts` selects the model, `agent/instructions.md` is the system prompt, and capabilities are added as directories (`tools/`, `schedules/`, `subagents/`, etc. — none exist yet beyond the two channels). This app is **not** where `detection-service`-style cron/query work belongs — that's a separate deployment by design (headless, no LLM, different trust boundary per `PLAN.md`).
