# Sentinel

**Team:** inputforge
**Track:** InMobi — Automated Root-Cause Analyst
**Team members:** [@recrsn](https://github.com/recrsn), [@roulpriya](https://github.com/roulpriya)

## Tagline

An ad-tech metrics watchdog that detects the anomaly in ClickHouse, drills
down to the responsible segment in ClickHouse, and only then hands the
evidence to an LLM to narrate — never the other way around.

## Hosted demo link

https://sentinel-ruby-alpha.vercel.app

## Demo video

https://www.loom.com/share/d595356a3b3a458db323213e796963d1

## Project description

Sentinel watches core InMobi ad-tech metrics — revenue, fill rate, eCPM,
CTR, requests — against a seasonal (same weekday/hour, trailing weeks)
baseline, and answers "why did this metric move?" with a plain-language,
evidence-backed diagnosis instead of a chart someone has to stare at.

The system is split into three stages that share one trace but never share
trust:

1. **Detection** — deterministic, no LLM. A chain of ClickHouse
   materialized views scores every metric/segment/hour against its seasonal
   baseline and writes qualifying deviations to `inmobi.anomalies` /
   `inmobi.incidents`. This is the boring, reproducible part on purpose —
   nothing here is tuned to any anomaly we've seen, since the system is
   scored on an unseen incident released separately.
2. **Investigation** — an agentic, tool-calling loop (an [eve](https://eve.dev)
   agent) that receives a flagged incident and decides *which* read-only
   ClickHouse query to run next: revenue-identity decomposition
   (requests × fill rate × eCPM), per-dimension attribution, pairwise
   cross-dimension attribution when a single dimension doesn't cover the
   delta, and explicit seasonality rule-outs. The LLM only narrates
   ClickHouse's numbers — it never computes one itself.
3. **Remediation** — advisory-only hypotheses (e.g. "fill-rate drop →
   check waterfall/demand partner"), kept structurally and visually
   separate from the evidence-backed diagnosis so a reviewer can never
   mistake a hypothesis for a computed number.

A Next.js dashboard (`apps/web`) surfaces incidents, drives the
investigation via a durable Vercel Workflow, and renders the resulting
diagnosis alongside the raw ClickHouse evidence it's grounded in.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full diagram and
component breakdown.

## Langfuse / ClickStack evidence

- Langfuse trace links (public, no login required): [`source_code/evidence/langfuse/traces.md`](./source_code/evidence/langfuse/traces.md)
- ClickStack trace search capture: [`source_code/evidence/clickstack/README.md`](./source_code/evidence/clickstack/README.md)

## Tech stack

- **ClickHouse** — primary datastore and the *only* place attribution math
  happens (materialized-view chain for detection; read-only tool-called
  queries for investigation).
- **[eve](https://eve.dev)** — agent framework for the investigation/
  remediation agent (`apps/sentinel-agent`), tool-calling loop, Slack +
  chat channels.
- **Vercel AI SDK** + OpenAI (`gpt-5.6-terra`) — the LLM used to select
  tools and narrate evidence.
- **Next.js 16 / React 19** (`apps/web`) — incident dashboard, incident
  detail pages, `/api/incident-analysis` route.
- **Vercel Workflow** — durable, resumable orchestration of the
  investigation run triggered from the dashboard.
- **Postgres** — stores durable agent analysis output only (not detection
  or incident qualification, which stay entirely in ClickHouse).
- **Langfuse** (`@langfuse/otel`, `@langfuse/vercel-ai-sdk`) — full
  investigation trace: every tool call, every ClickHouse query issued, and
  why. Self-hostable locally via [`docker-compose.yml`](./source_code/docker-compose.yml)
  + [`otel-collector-config.yaml`](./source_code/otel-collector-config.yaml)
  (OTLP on `14317`/`14318` → Langfuse), or point at Langfuse Cloud.
- **ClickStack / HyperDX** (`@hyperdx/browser`, OTLP export) — second
  observability surface for the same trace, writing the standard
  `otel_traces`/`otel_logs`/`otel_metrics` tables into ClickHouse via
  [`apps/detection-service/docker-compose.yml`](./source_code/apps/detection-service/docker-compose.yml)
  (OTLP on `4317`/`4318`).
- **Turborepo / pnpm** monorepo.

## Repo layout

```
source_code/
├── apps/
│   ├── detection-service/   Stage 1 — ClickHouse MV chain, no LLM
│   ├── sentinel-agent/      Stage 2/3 — eve agent, investigation + remediation
│   └── web/                 Dashboard — incidents list/detail, workflow trigger
├── packages/                 shared ui / eslint / tsconfig
├── notebooks/                 dataset exploration (ClickHouse + pandas)
├── PLAN.md                    design rationale for the three-stage split
└── CLAUDE.md                  repo map / architecture notes
```

## Local setup instructions

Requires Node 24, pnpm, and a ClickHouse instance.

```bash
cd source_code
pnpm install

# Detection service — needs CLICKHOUSE_URL / CLICKHOUSE_USER / CLICKHOUSE_PASSWORD
# in apps/detection-service/.env.local
cd apps/detection-service
npm run setup:local      # ClickHouse schema, detection_config seed, MV chain
npm run recompute:local  # force the refreshable MV chain to run now
npm run sweep:local      # print recent anomalies + current incident spans

# Sentinel agent — needs its own .env.local (OpenAI key, Langfuse/ClickStack
# keys optional), see apps/sentinel-agent/.env.example
cd ../sentinel-agent
pnpm dev

# Dashboard
cd ../web
pnpm dev
```

Root-level commands (via Turborepo, across all workspaces):
`pnpm build`, `pnpm dev`, `pnpm lint`, `pnpm check-types`, `pnpm format`.

## Pitch deck

[pitch-deck.pdf](./pitch-deck.pdf)
