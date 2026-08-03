# Infrastructure

This folder supports local development for the Schema Kings pipeline. The app
ClickHouse instance is the primary datastore for base data, generated Silver
tables, context memory, and pipeline tracking.

## Start App ClickHouse Only

```bash
docker compose up -d clickhouse
```

Useful URLs/ports:

- HTTP: `http://localhost:8123`
- Native: `localhost:9000`
- User: `schema_kings`
- Password: `schema_kings`

## Start ClickHouse + Langfuse

```bash
docker compose --profile langfuse up -d
```

Useful URLs/ports:

- App ClickHouse: `http://localhost:8123`
- Langfuse UI: `http://localhost:3000`
- Langfuse ClickHouse: `http://localhost:8124`
- MinIO console: `http://localhost:9091`

The Langfuse stack is intentionally separate from the app ClickHouse instance.
That keeps product analytics data separate from observability data.

## Environment Overrides

Copy `.env.docker.example` to `.env.docker` and run:

```bash
docker compose --env-file .env.docker up -d clickhouse
docker compose --env-file .env.docker --profile langfuse up -d
```

## App ClickHouse Databases

The app ClickHouse init scripts create:

- `bronze`
- `silver`
- `gold`
- `context`
- `ops`

Key tables:

```text
bronze.feature_specs
bronze.feature_events
gold.feature_metrics
gold.feature_insights
context.context_documents
context.feature_registry
context.fact_registry
context.contradictions
ops.pipeline_runs
ops.pipeline_stages
```

The provided Atlys base tables are loaded separately by `data/load.sh` into the
`schema_kings` database.

See [`../RUN.md`](../RUN.md) for reset, load, bootstrap, and demo commands.
