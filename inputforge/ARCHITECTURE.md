# Sentinel — Architecture

## Where analysis runs

All attribution math runs **inside ClickHouse**, never inside the LLM. The
LLM's role is limited to (a) choosing which read-only ClickHouse query to
run next during investigation, and (b) narrating the numbers ClickHouse
returns. This is a hard constraint from `PLAN.md`, not an implementation
detail — the InMobi track requires the drill-down to live in ClickHouse
queries.

```
inmobi.ad_events (fact table)
   │
   ├─▶ metrics_hourly / segment_metrics_hourly      (reactive MVs, fire on INSERT)
   │        │
   │        ▼
   │   metric_zr_hourly                              (refreshable MV, seasonal z-residual)
   │        │
   │        ▼
   │   inmobi.anomalies / inmobi.segment_anomalies    (refreshable MVs — trend_seasonal
   │        │                                          + proportion + day_level ensemble)
   │        ▼
   │   inmobi.incidents                               (refreshable MV — canonical, deduped spans)
   │        │
   ▼        ▼
apps/detection-service                          apps/web (dashboard)
(Stage 1 — no LLM, ClickHouse only)                   │
                                                        │ POST /api/incident-analysis
                                                        ▼
                                                 Vercel Workflow
                                              (durable, resumable)
                                                        │
                                                        ▼
                                          apps/sentinel-agent (eve agent)
                                       Stage 2 — Investigation (agentic loop)
                                       Stage 3 — Remediation (advisory only)
                                                        │
                                     tool-calling loop over read-only
                                     ClickHouse SELECTs (revenue-identity
                                     decomposition, Tier-1 per-dimension
                                     attribution, Tier-2 pairwise cross,
                                     seasonality rule-out)
                                                        │
                                                        ▼
                                          Postgres (incident_analysis —
                                          durable diagnosis storage only)
                                                        │
                                                        ▼
                                          Dashboard renders diagnosis +
                                          the ClickHouse evidence it cites
```

## Component integration

- **`apps/detection-service`** — Stage 1. Two execution models on purpose:
  - *Reactive*: the two single-hop rollups (`ad_events` → `metrics_hourly`,
    `ad_events` → `segment_metrics_hourly`) fire directly on `INSERT`.
    Proven reliable even under large bulk loads.
  - *Refreshable*: everything downstream (seasonal z-residual, the
    consolidated anomaly ensembles, canonical incidents) reschedules
    itself inside ClickHouse (`REFRESH EVERY ...`, chained via
    `DEPENDS ON`) and recomputes full history every cycle, rather than
    reacting to inserts. A cascaded reactive MV (one sourced from another
    MV's output, not `ad_events` directly) was found empirically to
    silently stop firing on a large bulk `INSERT`; refreshable sidesteps
    this by not depending on triggering at all.
  - No LLM, no cron poller, no outbound webhook in this service — it is
    deliberately "boring and reproducible."

- **`apps/sentinel-agent`** — Stage 2/3, an [eve](https://eve.dev) agent.
  Given a flagged incident, it runs a tool-calling loop:
  1. Revenue-identity decomposition
     (`Revenue ≈ Requests × Fill rate × eCPM / 1000`) to find which factor
     moved.
  2. Tier-1: rank every dimension (`ad_format, category, tier, vertical,
     campaign_type, region, country, device_model, os_version`)
     independently by contribution to the delta.
  3. Tier-2: pairwise, conditional — only if Tier-1's best single
     dimension doesn't cover most of the delta. Crosses only the top 2–3
     Tier-1 dimensions, not a full cross-product, with a min-support
     floor.
  4. Explicit rule-out checks, including seasonality (at least one planted
     movement in the eval set is pure seasonality and must be ruled out,
     not alarmed on).
  Every query is a single read-only `SELECT`/`WITH` with a numeric
  `LIMIT`. The LLM chooses which query to run next; it never computes a
  number itself. Stage 3 (remediation) consumes a completed diagnosis and
  maps factor + segment to advisory hypotheses only — kept structurally
  separate in both output and trace so a hypothesis can never be mistaken
  for a computed number.

- **`apps/web`** — dashboard. Lists incidents from `inmobi.incidents`,
  triggers investigation via a Vercel Workflow (`/api/incident-analysis`),
  and renders the resulting diagnosis next to the ClickHouse evidence it
  cites. Postgres holds only the durable `incident_analysis` output — not
  detection state or incident qualification, which live entirely in
  ClickHouse.

## Anomaly detection and attribution methodology

- Detection scores each metric/segment/hour against a **trailing 4-week,
  same-day-of-week, same-hour baseline** — never a fixed threshold —
  using an ensemble of `trend_seasonal`, `proportion`, and `day_level`
  methods globally (`trend_seasonal` + `proportion` only per segment).
  Ratio metrics (fill rate, render rate, CTR, eCPM, RPR) are always
  `sum / sum` over a group, never an average of per-row/per-day ratios.
- Attribution (Stage 2) starts from the revenue identity to localize
  *which factor* moved (volume, fill, or price), then ranks candidate
  segments by contribution to the delta, escalating to pairwise
  cross-dimension analysis only when a single dimension doesn't explain
  most of the movement. Segments under 3% of baseline volume are excluded
  from attribution; a top lift above 2x is called localized, otherwise the
  movement is reported as broad-based.
- Nothing in detection or investigation is tuned to specific anomalies
  seen during development — thresholds are statistical
  (z-score/seasonal-baseline), because the system is scored against an
  unseen incident released after development.

## Integration evidence — Langfuse & ClickStack

`apps/sentinel-agent/agent/instrumentation.ts` registers OpenTelemetry span
processors for **both** Langfuse and ClickStack/HyperDX simultaneously
(both are optional and independently enabled by env vars):

- **Langfuse** — `LangfuseSpanProcessor` (`@langfuse/otel`) exports every
  span; `LangfuseVercelAiSdkIntegration` (`@langfuse/vercel-ai-sdk`) is
  registered against the AI SDK's `registerTelemetry` so Langfuse can
  compute per-call token cost. A `presentationNameProcessor` renames
  machine-oriented span names (`query_clickhouse_evidence`, `chat ...`,
  `invoke_agent ...`, `step N`) to presentation-ready labels
  ("ClickHouse Evidence Query", "Sentinel Chat Orchestrator", "Delegate:
  Root-Cause Analyst", "Investigation Reasoning Step") before export, so
  a trace reads as the investigation story, not internal identifiers.
- **ClickStack** — a `BatchSpanProcessor` exports the same spans over
  OTLP/HTTP to HyperDX (`HYPERDX_API_KEY`, `HYPERDX_OTLP_ENDPOINT`).
  `apps/web` also loads `@hyperdx/browser` for client-side traces.

Configuration (secrets redacted) lives in
`apps/sentinel-agent/.env.example`; the wiring itself is in
`apps/sentinel-agent/agent/instrumentation.ts`.

## LLM provider selection and justification

OpenAI (`gpt-5.6-terra`, via `@ai-sdk/openai` + Vercel AI SDK) is used for
the investigation/remediation agent. The agent is constrained to a
tool-calling loop over a fixed set of read-only ClickHouse tools — model
choice affects *which query it picks next* and *how it narrates the
result*, not any numeric output, so the LLM is swappable behind the AI
SDK's provider interface without touching detection or attribution logic.

## Unseen incident bundle

The CLI/scan entry point sweeps a time range across all core metrics
(Stage 1), auto-runs Stage 2 on each flagged anomaly, and dumps structured
output plus Langfuse trace links — this is the reproducible path used to
produce the unseen-incident deliverable. Every figure in a diagnosis is
sourced from a numbered ClickHouse query in that trace, so it is
independently reproducible from `inmobi.ad_events`.
