# Operations Console (React + Vite + TypeScript)

The judge/operator-facing UI for the Automated Root-Cause Analyst. Served behind nginx at
**http://127.0.0.1** (port 80) in the docker-compose stack; talks to the FastAPI JSON API on `:8088`.

Zero configuration on the operations path: "now" is the data's own clock (`max(event_time)`),
so there are no date pickers to fill before the system tells you what's wrong.

## Routes

| Route | Page | Purpose |
|---|---|---|
| `/` | `pages/OpsHome.tsx` | Status bar ($/day at risk, data clock, sweep receipt) → revenue funnel over the exact revenue identity → work queue ranked by $/day |
| `/incidents/:id` | `pages/IncidentDetail.tsx` | Verdict → deterministic causal chain (above the LLM narration) → evidence score with published-formula breakdown → proof charts → ruled-out **with numbers** → member breaches → verbatim SQL trace → chat |
| `/investigations/:id` | `pages/InvestigationDetail.tsx` | A single investigation's evidence bundle: drill-down levels, ruled-out list, queries, narration |

## Dataset switcher

The header switcher (`components/DatasetSwitcher.tsx`, state in `lib/dataset.ts`) flips every
API call between the two ClickHouse databases — `main` (`ad_events_main`, the calibrated 9M-row
history) and `unseen` (`unseen_data`, the sealed Jul 6–10 incident drop) — via the `?dataset=`
query parameter. The list of datasets comes from `GET /api/datasets`, never from hardcoded
names, dates or row counts.

## Notable components

- `RevenueFunnel.tsx` / `MetricTrendChart.tsx` / `BandChart.tsx` — the metric tree and actual-vs-seasonal-band charts
- `CausalChain.tsx` — the deterministic because-ladder diagnosis (no LLM)
- `WaterfallChart.tsx` — the 4-factor revenue decomposition, residual shown
- `SpreadBars.tsx` / `SiblingBars.tsx` / `ImpactBars.tsx` — the localisation, seasonality-disproof and exposure arguments
- `EvidenceScore.tsx` — the 0–100 evidence index with its published fixed-weight formula and per-component arithmetic
- `GrainLadder.tsx` — per-grain verdict chips, where "no band" is a distinct state that never reads as green
- `SqlTrace.tsx` — every query verbatim, with scanned-row counts
- `Chat.tsx` — follow-up questions grounded in the incident's own evidence
- `IncidentQueue.tsx` / `KeyFindings.tsx` / `Recommendations.tsx` / `RuledOutList.tsx` / `OwnerBadge.tsx` — the work queue and its supporting surfaces

Shared logic lives in `src/lib/` (`format.ts`, `status.ts`, `metricConfig.ts`, `viewMode.ts`
for the Summary / Full-evidence toggle, `motion.ts`) and all HTTP goes through
`src/api/client.ts`.

## Develop

```bash
npm install
npm run dev        # Vite dev server; proxies /api, /investigate, /healthz to 127.0.0.1:8088
npm run build      # tsc -b && vite build
npm run lint       # oxlint
```

The dev proxy (`vite.config.ts`) mirrors the production nginx reverse proxy (`nginx.conf`),
so no app code differs between dev and the container — the UI always calls relative paths.
