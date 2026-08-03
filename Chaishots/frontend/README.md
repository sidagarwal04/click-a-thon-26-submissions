# Clickathon Run Explorer

A focused React/Vite interface for reading Clickathon pipeline traces from Langfuse. Langfuse credentials stay in the FastAPI backend; this app only calls the read-only observability routes.

## Run locally

Start the backend from the `clickhouse` repository:

```bash
cd ../clickhouse/backend
uv run uvicorn app.main:app --reload --port 8000
```

Then start the frontend:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>. Vite proxies `/api` to the backend. To use another backend, set `VITE_API_BASE_URL` (including `/api/v1`).

Use **New run** in the top navigation, or open <http://localhost:3000/new-run>,
to select a feature key, `spec.md`, and `events.ndjson`. The page uploads both
files, starts `/features/process`, shows pipeline progress, waits for Langfuse to
publish the trace, and then opens the new run automatically.

## What the explorer shows

- Every Langfuse trace as a searchable run history
- Status, duration, observation count, cost, environment, trace and pipeline IDs
- Chronological waterfall of each pipeline stage and agent call
- Expandable input, output, metadata, usage, and error details
- Full root input/output/metadata payloads with copy and fullscreen controls
- ClickHouse-backed overview with rows loaded, destination table, and context version
- Event distribution and field profiling with presence/cardinality summaries
- Instrumentation contract, generated schema, funnel steps, and executed DDL
- Context relationships, reusable metric definitions, and conflicts
- Agent-proposed versus validated SQL analyses and aggregate result matrices
- Full evidence, interpretation, recommendations, confidence, and caveats for insights
