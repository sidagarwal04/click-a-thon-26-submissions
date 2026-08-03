# Clickathon Docker stack
#
# Reuses LibreChat + MCP + Admin Panel from ClickHouse agentic-data-stack,
# with Langfuse Cloud + ClickHouse Cloud (no local Langfuse/CH for app data).
# Adds ClickStack (HyperDX + OTel) writing telemetry into ClickHouse Cloud.
#
## Prerequisites
- Docker Compose v2+
- Root `.env` filled (see `../.env.example`)

## Start

```bash
# from repo root
docker compose -f stack/docker-compose.yml --env-file .env up -d
```

## URLs

| Service | URL |
|---|---|
| LibreChat | http://localhost:3080 |
| Admin Panel | http://localhost:3081 |
| HyperDX (ClickStack) | http://localhost:8080 |
| ClickHouse MCP | http://localhost:8000/mcp |
| **RCA MCP** | http://localhost:8001/mcp |
| OTLP HTTP | http://localhost:4318 |
| Langfuse | https://cloud.langfuse.com (Cloud) |

Default LibreChat admin (from `.env`): see `LIBRECHAT_USER_*`.

HyperDX login: `admin@clickathon.local` / same password as `LIBRECHAT_USER_PASSWORD`.

### ClickStack notes

- Logs source must use `Timestamp` (Cloud `otel.otel_logs` has no `TimestampTime`).
- OTLP ingest requires `authorization: <HYPERDX_API_KEY>` (team API key). Without it the collector returns **401**.
- HyperDX API listens on **8002** (not 8000 — that port is ClickHouse MCP).
- **LibreChat → HyperDX:** `librechat-log-shipper` tails `/app/logs` (`error-*.log`, `debug-*.log`) and exports OTLP to the ClickStack collector. Filter HyperDX Logs by `ServiceName:librechat`.

## LibreChat RCA (important)

ModelSpecs use persisted **Agents** with Orchestrator → Detector / Factor / Localizer **subagents**.

```bash
# after DB wipe / first setup
uv run python stack/scripts/seed_librechat_agents.py
docker compose -f stack/docker-compose.yml --env-file .env up -d --force-recreate librechat
```

1. Open http://localhost:3080
2. Select **InMobi RCA Orchestrator**
3. Ask: `What are the anomalies?` (reads `eda.rca_incidents`) or `Investigate 2026-06-23…`

### ClickHouse-native RCA tables

Anomalies are **assembled entirely in ClickHouse SQL** (`eda.rca_*`): dictionaries, seasonality z-scores, gap-and-island clustering, counterfactuals. The LLM only narrates.

```bash
uv run clickathon materialize                 # rebuild rca_* from current eda data
uv run clickathon materialize --rollup        # also rebuild metrics_hourly from ad_events
uv run clickathon materialize --check --calibration
```

See [`sql/README.md`](../sql/README.md) for the new-test-file playbook.

Agents: `list_all_anomalies` → catalog; `explain_anomaly(incident_id)` → detailed RCA; `counterfactual(incident_id)` → what-if revenues; dig with ClickHouse MCP on `rca_segment_day` / `rca_combo_day` / `rca_counterfactual`.

### Metrics glossary (locked Click-a-thon repo)

Same idea as [ClickHouse AI-first DWH](https://clickhouse.com/blog/ai-first-data-warehouse) — glossary via MCP — but **scoped to one repo only**.

Agents use Clickathon-RCA tools (no general GitHub MCP, no PAT required):

- `get_metrics_glossary_tool` → [`InMobi/metrics_glossary.md`](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/InMobi/metrics_glossary.md)
- `get_clickathon_github_file(path)` → any path **inside** `sidagarwal04/click-a-thon-2026` only (other owners/repos are rejected)

### Langfuse verification

ClickHouse SQL from RCA MCP is logged as Langfuse spans named `clickhouse.query`.
LibreChat chats appear as Langfuse **sessions** (thread id = session id).

Agents can call:

- `get_latest_langfuse_trace_tool` — **"give me the trace for this"** (no id needed)
- `get_langfuse_trace_tool(trace_id)` — specific trace
- `list_langfuse_sessions_tool` / `get_langfuse_session_tool(session_id)`
- `list_langfuse_clickhouse_queries_tool`

Ask: `Give me the trace for this` or `List recent Langfuse sessions and verify SQL.`

## CLI (same engine)

```bash
uv run clickathon materialize
uv run clickathon scan                 # reads rca_incidents when present
uv run clickathon investigate 2026-06-23
uv run clickathon mcp --port 8001   # local RCA MCP (Compose also runs this)
```

## Stop

```bash
docker compose -f stack/docker-compose.yml --env-file .env down
```

## Notes

- HyperDX API listens on **8002** so it does not clash with MCP on **8000**.
- OTel data is written to database `otel` on ClickHouse Cloud (create if missing).
# LibreChat + MCP + Admin + ClickStack (no RAG / Meilisearch).
# Create an admin user once with: ./scripts/create-librechat-user.sh
# Attribution: agentic-data-stack (Apache-2.0) + ClickStack.
