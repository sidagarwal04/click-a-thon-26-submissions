# Observability (ClickStack)

ClickStack watches the pipeline itself: ingest latency, insert batch sizes, benchmark
query p95, and error counts, all landing in ClickHouse `otel_*` tables where
HyperDX / ClickStack dashboards read them.

```
pipeline scripts --OTLP :4318--> clickstack-otel-collector --> ClickHouse otel_* --> HyperDX
Vector collector --Prometheus :9598--------------------------------^ (scrape/import)
```

## Run
```bash
cp .env.example .env      # ClickHouse endpoint the telemetry lands in + OTLP settings
docker compose up -d      # OTLP on :4317 (gRPC) / :4318 (HTTP)
```

## Instrumented client (`ingester/`)
A thin wrapper around clickhouse-connect: every insert / query / command is traced and
timed into ClickStack automatically. Use it wherever the pipeline talks to ClickHouse:

```bash
cd ingester && uv sync
uv run python examples/peak_concurrency.py   # traced benchmark queries -> HyperDX
```

```python
from ingester import get_clickhouse, span

ch = get_clickhouse()                        # connects + starts telemetry
rows = ch.query_rows("SELECT max(c) FROM (SELECT minute, sum(cnt) c "
                     "FROM sonyliv.hist_minute_full GROUP BY minute)",
                     table="hist_minute_full")

with span("backfill.hist", {"day": "2026-07-31"}):
    ch.command(open("sql/02_backfill_hist.sql").read())
```

`TELEMETRY_ENABLED=false` turns the whole thing into a no-op; the code path is unchanged.

## What we watch in HyperDX
- **Ingest lag + insert batches**: `ingester.insert.duration` / `ingester.insert.rows`,
  plus the Vector collector's own metrics (`:9598`) for the streaming path.
- **Benchmark p95**: `ingester.query.duration` per table; serving queries must stay
  dashboard-grade, and regressions show up here before judges see them.
- **Dashboard + LibreChat queries**: the UI proxy tags every query with
  `log_comment = 'frontrow-dashboard'` (`ui/server.mjs`) and the LibreChat MCP sidecar
  runs under its own ClickHouse user, so per-consumer latency/rows-read splits cleanly
  in query telemetry: `SELECT ... FROM system.query_log WHERE log_comment = 'frontrow-dashboard'`
  or `WHERE user = 'llm_readonly'`.
- **What queries actually read**: spans carry the SQL, cross-checked against
  `system.query_log` rows/bytes read to prove queries hit `hist_minute_full`, not raw history.
