# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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
npm run sweep:local     # prints recent anomalies + current incident spans (there's no sweep to trigger anymore — see sql/mv/README.md)
npm run incidents:local # prints current incident spans only
npm start                 # runs the persistent process: just the 10-min incident/webhook poll now
npm run check-types
```
These need `CLICKHOUSE_URL` / `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` in `apps/detection-service/.env.local` (gitignored, not committed — ask the user for these rather than inventing them).

There is no test suite anywhere in this repo yet.

## Architecture: `apps/detection-service`

No LLM, "boring and reproducible" by design (`PLAN.md`'s explicit instruction for Stage 1). Three different execution models, deliberately:

- **Reactive** — `sql/mv/`: a chain of ClickHouse materialized views triggered by `INSERT`s into `inmobi.ad_events`, both global and segment-level. Global (`01`–`05`): raw events roll up into `metrics_hourly`, which feeds the seasonal z-residual (`metric_zr_hourly`), which feeds `trend_seasonal`/`proportion`/`day_level` detection straight into `anomalies`. Segment-level (`07`–`10`): the same shape one level deeper, into `segment_metrics_hourly` → `segment_anomalies` (7 dimensions × `trend_seasonal`/`proportion`, not `day_level`/`cusum` — see below). No cron, no polling — see `sql/mv/README.md` for the full chain, including why it's safe under a bulk multi-hour data load (each touched hour, or touched (dimension,segment,hour) triple, looks up its own trailing baseline independently, no cross-hour ordering dependency).
- **Refreshable** — `sql/mv/06_mv_noise_baseline_daily.sql`: a `REFRESH EVERY 1 DAY` materialized view (ClickHouse's own scheduler, not app-level cron) for the pooled residual-noise baseline that `trend_seasonal` shrinks toward.
- **Scheduled** — `lib/incremental/scheduler.ts` (`node-cron`, kept alive by `index.ts`) for the one thing left that can't be either kind of MV: a 10-minute poll that recomputes incident spans directly from `inmobi.anomalies` and fires `DETECTION_WEBHOOK_URL` on a state change (new incident opened / resolved). No separate incident store — dedup is process-local in-memory state (`lib/incremental/incidents.ts`), not Postgres. Detection itself (global and segment-level) has no scheduled component at all anymore.
- `lib/clickhouse.ts` — thin wrapper around the official `@clickhouse/client` SDK, used by setup and the scheduled poll.
- `cusum` is dropped from the active ensemble (`detection_config`'s cusum rows seeded `enabled=0`, `cusum_state` table kept but unwritten) — it's a true sequential recurrence, and a block-triggered MV can't fold it correctly under a bulk multi-hour load; a different algorithm is expected to fill this gap. `basic`/`ewma_fast`/`ewma_slow` remain dormant for unrelated reasons (see `sql/01_detection_config_seed.sql`'s comments) — active global ensemble is `trend_seasonal` + `proportion` + `day_level`; active segment ensemble is `trend_seasonal` + `proportion` only (day_level/cusum were never run per segment, even in the old batch design).
- `anomalies`/`segment_anomalies` are `ReplacingMergeTree`, keyed on `(metric, method, time_window)` / `(dimension, segment, metric, method, time_window)` respectively, **not** truncated between runs — a reprocessed hour replaces that row instead of duplicating, so both tables are a standing audit trail / Stage 2 work queue. Query with `FINAL` to see the deduped state.

**To add a new metric or query:** if it's a ratio derivable from existing `metrics_hourly`/`segment_metrics_hourly` columns, it's a same-shape line added to the `UNION ALL` blocks in the relevant `sql/mv/*.sql` file(s), plus a few threshold rows in `sql/01_detection_config_seed.sql` — no TypeScript changes, but changing an MV's query means dropping and recreating it (`CREATE OR REPLACE` doesn't apply to MVs the same way; see `sql/mv/README.md`). A wholly new detection *method* needs a new MV (or a scheduled `.sql` file, if it's not block-safe like `cusum`) and, only if scheduled rather than reactive, one line added to `lib/incremental/scheduler.ts`. A metric needing a raw signal not yet in `ad_events` is out of this service's scope (upstream data pipeline).

**Ratio-metric rule, load-bearing everywhere in `sql/`:** fill rate, render rate, CTR, eCPM, RPR must always be computed as `sum / sum` over a group, never as an average of per-row or per-day ratios — getting this wrong silently corrupts every rollup. This mirrors the metrics glossary the source dataset ships with.

## Architecture: `apps/sentinel-agent`

Standard [eve](https://eve.dev) project layout — read `node_modules/eve/docs/README.md` before adding capabilities. `agent/agent.ts` selects the model, `agent/instructions.md` is the system prompt, and capabilities are added as directories (`tools/`, `schedules/`, `subagents/`, etc. — none exist yet beyond the two channels). This app is **not** where `detection-service`-style cron/query work belongs — that's a separate deployment by design (headless, no LLM, different trust boundary per `PLAN.md`).
