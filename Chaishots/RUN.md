# Running Asklys

This guide covers local application startup, service configuration, feature
processing, manual startup, and verification.

## Fastest path

From the repository root, run:

```bash
./dev.sh
```

The launcher will:

1. verify that `uv`, `npm`, `curl`, and `lsof` are available;
2. create `.env.local` from `.env.example` when no environment file exists;
3. synchronize the locked Python environment with `uv`;
4. run `npm ci` when frontend dependencies are missing or outdated;
5. start FastAPI on port `8000`;
6. start Vite on port `3000`;
7. verify the backend health endpoint through the Vite `/api` proxy; and
8. stop both processes when you press Ctrl+C.

Once the ready message appears, open:

- Application: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- Backend health check: <http://localhost:8000/api/v1/utils/health-check/>

Starting the application does not run an agent pipeline or write to ClickHouse.

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 20 or newer
- npm
- `curl` and `lsof` (included with macOS)

For actual feature processing, you also need:

- a ClickHouse Cloud service containing the eight supplied Atlys baseline
  tables;
- a Fireworks API key; and
- Langfuse credentials when trace capture is enabled.

The required baseline tables are:

```text
application_started
auth_completed
destination_card_clicked
document_uploaded
landing_page_scrolled
pay_now_clicked
purchase_completed
search_typed
```

## Environment configuration

If neither `.env` nor `.env.local` exists, `./dev.sh` creates an ignored
`.env.local` automatically. To create it yourself:

```bash
cp .env.example .env.local
```

Add the following values before processing features:

```dotenv
CLICKHOUSE_HOST=your-service.region.provider.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=replace-locally
CLICKHOUSE_DATABASE=atlys
CLICKHOUSE_SECURE=true

FIREWORKS_API_KEY=replace-locally

LANGFUSE_TRACING_ENABLED=true
LANGFUSE_PUBLIC_KEY=replace-locally
LANGFUSE_SECRET_KEY=replace-locally
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Never put credentials in the checked-in `.env` template; secrets belong only
in the ignored `.env.local`, which is loaded after `.env` and overrides it.

## Start the local application

```bash
./dev.sh
```

To use different ports:

```bash
BACKEND_PORT=8100 FRONTEND_PORT=3100 ./dev.sh
```

The launcher sets `VITE_API_PROXY_TARGET` automatically, so the browser always
sends `/api` requests to the backend port selected for that invocation.

## Process a feature

> This command writes to ClickHouse and invokes the configured model and trace
> services. Run it only after the target ClickHouse environment is ready.

Create a feature folder containing exactly these input files:

```text
incoming_features/<feature>/
├── spec.md
└── events.ndjson
```

Then run the complete pipeline:

```bash
uv run --project backend atlys-pipeline --feature <feature>
```

Example:

```bash
uv run --project backend atlys-pipeline \
  --feature 06_promo_coupon_checkout
```

The command profiles the event file, generates and validates DDL, creates or
reuses the feature table, inserts events, updates semantic context, executes
validated aggregate analytics, stores artifacts, and flushes the Langfuse
trace. Its JSON output includes the run ID, table, inserted row count, context
version, insights, and trace ID.

The same operation is available through:

- `POST /api/v1/features/process` in the REST API; or
- `process_feature` through the MCP server.

## Manual startup

Use this only when you want separate terminals or more control over logs.

Terminal 1, from the repository root:

```bash
uv sync --project backend --locked
uv run --project backend uvicorn app.main:app \
  --host 0.0.0.0 --port 8000
```

Terminal 2, from the repository root:

```bash
npm --prefix frontend ci
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 \
  npm --prefix frontend run dev -- \
  --host 0.0.0.0 --port 3000 --strictPort
```

## Optional MCP server

Start the local stdio MCP adapter with:

```bash
uv run --project backend atlys-mcp
```

For the Streamable HTTP transport used by LibreChat:

```bash
MCP_TRANSPORT=streamable-http \
MCP_HOST=127.0.0.1 \
MCP_PORT=8001 \
uv run --project backend atlys-mcp
```

The endpoint is then available at <http://localhost:8001/mcp>.

## Troubleshooting

### Port 3000 or 8000 is already in use

The launcher prints the process holding the port. Stop that process or select
different ports:

```bash
BACKEND_PORT=8100 FRONTEND_PORT=3100 ./dev.sh
```

### Frontend packages are broken or incomplete

Recreate the locked dependency tree:

```bash
npm --prefix frontend ci
```

### The UI starts but data requests fail

Confirm the backend is healthy:

```bash
curl --fail http://localhost:8000/api/v1/utils/health-check/
```

Then verify `.env.local` contains the service credentials needed for the
operation you are attempting. Application startup alone does not require a
ClickHouse connection.

### Traces are missing

Check that `LANGFUSE_TRACING_ENABLED=true` and that the public key, secret key,
and base URL belong to the same Langfuse project.

## Verify before submission

Backend:

```bash
cd backend
../.venv/bin/pytest -q
../.venv/bin/ruff check app tests
../.venv/bin/mypy app
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

For architecture, security boundaries, context freshness, agent contracts, and
artifact endpoints, see [ARCHITECTURE.md](./ARCHITECTURE.md).
