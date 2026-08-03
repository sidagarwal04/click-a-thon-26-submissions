# Atlys feature analytics architecture

The application has one use-case boundary:

```text
REST API ─┐
MCP tools ├── process_feature_pipeline() ── FeaturePipelineService ── ClickHouse
CLI ──────┘
```

A custom dashboard should call the REST API. LibreChat should call the MCP
server. The CLI is useful for deterministic smoke tests. All three adapters call
the same Python service; none contains pipeline or agent logic.

## Scope

The eight baseline Atlys event tables are assumed to already exist in the
configured ClickHouse database. This repository does not load Parquet files or
bootstrap those tables.

New feature ingestion remains part of the later pipeline stages. A feature input
is placed under `incoming_features/<feature>/` with `spec.md` and
`events.ndjson`. Paths are root-contained and the NDJSON file is streamed with
bounded memory. Raw rows are not returned to REST/MCP callers or captured by
Langfuse.

API and dashboard callers can create that folder with the multipart upload
route. It requires files named exactly `spec.md` and `events.ndjson`, enforces
byte limits, and refuses to overwrite an existing feature folder. Uploading does
not start processing; the caller separately invokes `/features/process`.

## Processing pipeline

`process_feature_pipeline(feature_folder)` performs the complete workflow:

1. Validate and resolve the feature folder.
2. Read a size-bounded UTF-8 specification.
3. Stream and profile NDJSON fields, event names, types, presence, examples, and
   bounded-cardinality estimates.
4. Verify ClickHouse with `SELECT 1` and inspect the existing table catalog.
5. Ask the Fireworks Instrumentation Agent for a structured feature contract and
   schema, then validate every field, type, identifier, nullable rule, funnel
   step, and ordering key in Python.
6. Create or safely reuse the feature table and stream NDJSON into typed
   ClickHouse batches while retaining `raw_payload`.
7. Ask the Context Agent for relationships, metrics, conflicts, and a new context
   version, then store the versioned diff.
8. Ask the Analytics Agent to select an analysis plan. Python builds and
   validates the executable funnel, adoption, OTP, latency, and baseline SQL
   primitives, enforces SELECT-only table allowlists and result limits, and runs
   them in ClickHouse.
9. Ask the Analytics Agent to interpret only those aggregate results, store every
   artifact, and write a final `completed` run snapshot.
10. Trace every stage and agent observation in Langfuse using bounded metadata.

Retries are resumable: an existing generated table is reused only when its
schema and row count exactly match the validated proposal and input profile.

## Context storage

The semantic context lives in ClickHouse itself, in a `context_versions` table
next to the event data, with generated run artifacts in `generated_artifacts`.
Every version is written as a complete document, so any historical snapshot is
read directly instead of being replayed from diffs, and the before/after
changelog for a new table is a two-row query. ClickHouse was chosen over a file
or vector store because the context must share the warehouse's durability and
access control, be queryable by the same client the agents already hold, and
version atomically with the runs that produced it. No similarity search is
needed — the context is small, structured, and read in full — so a vector
store would add infrastructure without adding capability.

## LLM provider

All three agents call Fireworks AI serving `gpt-oss-120b` through its
OpenAI-compatible endpoint. The rationale: the pipeline needs strict
structured-output (JSON schema) support because every agent response is parsed
into typed Pydantic contracts and rejected on violation; an open-weights model
keeps the system portable to self-hosting; and Fireworks' latency and cost
profile suits a pipeline that makes several sequential agent calls per feature.
The provider is one `FIREWORKS_BASE_URL`/`FIREWORKS_MODEL` pair in
configuration, so any OpenAI-compatible endpoint can be substituted without
code changes.

## Public interfaces

REST routes are under `/api/v1`:

- `POST /features/upload` (multipart `feature_folder`, `spec`, and `events`)
- `POST /features/process`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/schema`
- `GET /runs/{run_id}/context-diff`
- `GET /runs/{run_id}/insights`

The custom MCP exposes the corresponding tools:

- `process_feature`
- `get_run_summary`
- `get_schema`
- `get_context_diff`
- `get_insights`

Schema and context artifacts return `404`/an MCP tool error until their stages
have generated them. Partial work is never fabricated as a completed run.

## Configuration

For local development, put secrets in the ignored `.env.local` file, not the
checked-in template `.env`:

```dotenv
CLICKHOUSE_HOST=your-service.region.provider.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=replace-locally
CLICKHOUSE_DATABASE=atlys
CLICKHOUSE_SECURE=true

LANGFUSE_TRACING_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com

FIREWORKS_API_KEY=
```

The password is passed to `clickhouse_connect.get_client()` lazily. Importing the
FastAPI app or running its health check does not require ClickHouse credentials.

## Running each adapter

From `backend/`:

```bash
# CLI
uv run atlys-pipeline --feature 01_express_checkout

# Equivalent script form
uv run python run_pipeline.py --feature 01_express_checkout

# Local stdio MCP server
uv run atlys-mcp

# REST API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Upload a new feature from another terminal:

```bash
curl -X POST http://localhost:8000/api/v1/features/upload \
  -F 'feature_folder=01_express_checkout' \
  -F 'spec=@/path/to/spec.md;type=text/markdown' \
  -F 'events=@/path/to/events.ndjson;type=application/x-ndjson'
```

Docker Compose runs REST on port `8000` and a Streamable HTTP MCP server on port
`8001`. A host-native LibreChat connects to `http://localhost:8001/mcp`. A
containerized LibreChat must join this Compose network and use
`http://mcp:8001/mcp`; `localhost` inside that container refers to LibreChat
itself.

Compose loads the checked-in defaults followed by the optional, ignored
`.env.local`, so this is sufficient:

```bash
docker compose watch
```

The MCP implementation uses the official Python SDK v2 `MCPServer`. The older
`FastMCP` import in the original design note belongs to the v1 SDK.
