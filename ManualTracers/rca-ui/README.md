# RCA UI

Standalone viewer for RCA agent reports — recent incidents, structured sections, filterable charts.

## Quick start (Docker — recommended)

```bash
docker compose up --build -d
```

Open http://localhost:8090

## Local development

```bash
# Terminal 1 — API (port 3002)
cd rca-api && npm install && npm start

# Terminal 2 — UI (port 5174)
cd rca-ui && npm install && npm run dev
```

Open http://localhost:5174

## Sample reports

Two incidents from the sealed dataset (see `rca-api/sample-reports.js`):

| ID | Incident |
|----|----------|
| `rca-android15-fill` | Global fill rate drop, Android 15 localized (Jun 23–25) |
| `rca-ios181-fill` | Fill rate dip, iOS 18.1 cohort (Jun 29–30) |

## Report sections

1. **What triggered this RCA** — alert, metric, window, signal strength
2. **What went wrong** — global movement summary
3. **Why it happened** — localized culprit + holdout confirmation
4. **Supporting data** — candidate table, contribution chart, time series
5. **Checked and ruled out** — near-misses with reasons

Charts share a filter toolbar (date range, granularity, OS filter).

Template spec: `docs/RCA_UI_TEMPLATE.md`

## Stack

- **rca-ui** — React 19 + Vite + shadcn/ui + Recharts (styled like dashboard template)
- **rca-api** — Express, serves ledger-shaped JSON + mock series until wired to live ClickHouse reproduce queries
