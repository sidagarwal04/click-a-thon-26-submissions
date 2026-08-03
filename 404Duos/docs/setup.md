# Setup & run

## Prerequisites

- Node.js 20+
- ClickHouse Cloud (or compatible) database `insightiq` with the InsightIQ schema and data
- Optional: Gemini API key, Langfuse

## Environment

### `apps/api/.env`

```bash
PORT=4000
CLICKHOUSE_HOST=<host>
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=<secret>
CLICKHOUSE_DATABASE=insightiq
CLICKHOUSE_SECURE=true
CLICKHOUSE_LOG_QUERIES=true
GEMINI_API_KEY=<optional>
GEMINI_MODEL=gemini-flash-lite-latest
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=https://jp.cloud.langfuse.com
```

### `apps/web/.env`

```bash
VITE_API_URL=http://localhost:4000
```

## Start services

```bash
# API (includes ClickHouse RCA engine in-process)
cd apps/api && npm install && npm run dev

# Web
cd apps/web && npm install && npm run dev
```

| Service | URL |
|---------|-----|
| Web | http://localhost:5173 |
| API | http://localhost:4000 |

```bash
curl -s http://127.0.0.1:4000/health
```

## Public demo

Railway (single API service) + Vercel web: [deploy.md](./deploy.md).

## Verify the ClickHouse cascade

```sql
SELECT title, detail, impact
FROM insightiq.alert_observations
ORDER BY abs(impact) DESC
LIMIT 5;

SELECT count() FROM insightiq.alerts_live WHERE abs(zscore) > 3;
```

Full cascade: [pipeline.md](./pipeline.md).

## Investigation export CLI

```bash
node scripts/export-investigation.mjs --list
node scripts/export-investigation.mjs --alertId=<UUID> --out=./exports
```

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Empty `/api/alerts` | No rows in `alerts_live`, or ClickHouse env wrong |
| API fails to start | `CLICKHOUSE_*` ping failed |
| Chat wrong date window | Pass an explicit date, or ensure snapshot `dataRange` is populated |
