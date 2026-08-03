# Sentinel — InMobi automated root-cause analyst

Sentinel detects statistically unusual ad-tech delivery metrics in ClickHouse,
then lets an evidence-grounded agent investigate the affected period. The
detector never uses an LLM; the investigator can only draw numerical claims
from its ClickHouse tools.

## Architecture

```text
inmobi.ad_events
  -> ClickHouse materialized views -> anomalies / segment_anomalies / incidents
  -> Sentinel agent -> scoped ClickHouse evidence queries -> diagnosis
                       |                         |
                       |                         +-> Langfuse trace (queries, tools, model usage)
                       +-> ClickStack OTLP collector -> ClickHouse otel_traces / otel_logs / otel_metrics
```

Stage 1 (`apps/detection-service`) is ClickHouse-native: reactive and
refreshable materialized views create the anomaly and incident work queues.
Stage 2 (`apps/sentinel-agent`) performs the investigation. Its tools query
the detected time window and contributing segments; the LLM narrates the
returned evidence rather than calculating metrics itself.

### OSS observability services

Langfuse is part of the investigation workflow, not a passive dependency.
[`agent/instrumentation.ts`](apps/sentinel-agent/agent/instrumentation.ts)
registers `LangfuseSpanProcessor` and the AI SDK integration. Each agent
trace therefore records the investigation orchestrator, delegated analyst,
ClickHouse tool calls, reasoning steps, model usage, and their parent-child
relationships. The local stack in [`docker-compose.yml`](docker-compose.yml)
starts self-hosted Langfuse and its required PostgreSQL, ClickHouse, Redis,
and MinIO services. [`otel-collector-config.yaml`](otel-collector-config.yaml)
also accepts OTLP on host ports `14317`/`14318` and forwards it to that
Langfuse project. The non-default ports avoid clashing with ClickStack.

ClickStack captures operational telemetry separately from the Langfuse
investigation record. The collector configuration in
[`apps/detection-service/docker-compose.yml`](apps/detection-service/docker-compose.yml)
accepts OTLP/gRPC (`4317`) and OTLP/HTTP (`4318`) and writes to the ClickHouse
instance set by `CLICKHOUSE_URL`. The ClickStack schema is the standard
`otel_traces`, `otel_logs`, and `otel_metrics` tables in that ClickHouse
database. With `HYPERDX_API_KEY` and `HYPERDX_OTLP_ENDPOINT` configured, the
same spans are exported by the agent's `clickstackProcessor`; local ClickStack
can use `HYPERDX_API_KEY=local` and `HYPERDX_OTLP_ENDPOINT=http://localhost:4318`.

LibreChat is not used by this project.

## Local observability setup

```sh
# Start self-hosted Langfuse and the OTLP-to-Langfuse collector.
docker compose up -d

# In apps/sentinel-agent/.env.local, set the local development values from
# apps/sentinel-agent/.env.example, then start the agent normally.
```

Open Langfuse at `http://localhost:3001` (or `LANGFUSE_PORT` if overridden).
The Compose file pre-seeds a local
development user (`admin@sentinel.local` / `sentinel-local-password`) and a
project. These credentials are deliberately public development values; replace
all of them before deploying outside a local machine.

For ClickStack, add real ClickHouse credentials to
`apps/detection-service/.env.local`, then run:

```sh
cd apps/detection-service
docker compose --env-file .env.local up -d clickstack-otel-collector
```

## Submission evidence

Do not require judges to log in to Langfuse. For every graded investigation,
place either its public Langfuse share link or a JSON export in
[`evidence/langfuse/`](evidence/langfuse/), and link it from this README.
Capture the ClickStack trace search or dashboard used during that same run in
[`evidence/clickstack/`](evidence/clickstack/), then add it here and show the
same flow in the hosted demo/video. The committed folders contain only
instructions until a real graded run is produced; no synthetic evidence is
included.

## Further documentation

- [`apps/detection-service/README.md`](apps/detection-service/README.md) —
  detection method, schema, and operational commands.
- [`PLAN.md`](PLAN.md) — trust boundaries and the intended investigation
  strategy.
