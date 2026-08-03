# ingester

A thin, ClickStack-instrumented **wrapper** around clickhouse-connect.

It does **not** own the pipeline or business logic. It hands you a drop-in
client that is automatically traced and timed into ClickStack, so anyone adding
a query or an ingest path gets insert/query performance telemetry for free:
just import and use the client as you normally would.

## Install

```bash
cd ingester
uv sync
```

Config comes from `.env` (resolved upward from the working directory via
`find_dotenv`; see `observability/.env.example`). Telemetry is built on the
official ClickStack SDK (`hyperdx-opentelemetry`): the app speaks OTLP to the
local `clickstack-otel-collector` (see `../docker-compose.yml`), which forwards
to ClickHouse.

## Use it: a new query

```python
from ingester import get_clickhouse

ch = get_clickhouse()                       # connects + starts telemetry
rows = ch.query_rows("SELECT count() FROM sonyliv.raw_events")
```

`insert()`, `query()`, `query_rows()` and `command()` are wrapped (span + timing).
Anything else is proxied straight to the underlying clickhouse-connect client
(`ch.query_df(...)`, `ch.raw`, ...), so it's a genuine drop-in.

## Instrument your own steps

```python
from ingester import span, traced

with span("backfill.hist", {"day": "2026-07-31"}):
    run_backfill()

@traced()
def build_serving_layer():
    ...
```

## What lands in ClickStack

| Instrument | What it shows |
|---|---|
| `ingester.insert.duration` / `.rows` / `.batches` | ingest latency + throughput |
| `ingester.query.duration` / `.rows` | benchmark/serving query latency (p95 in HyperDX) |
| `ingester.errors` | failures by operation/table |
| spans `clickhouse.insert` / `.query` / `.command` | per-call traces with SQL + row counts |

`TELEMETRY_ENABLED=false` makes everything a no-op; the calling code is unchanged.

Try it: `uv run python examples/peak_concurrency.py` runs the headline benchmark
queries through the wrapper, so the latencies land in HyperDX as evidence.
