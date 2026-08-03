# ClickStack evidence

ClickStack (HyperDX + OTel collector) is wired in `source_code/stack/clickstack-compose.yml`. Runtime telemetry lands in **ClickHouse Cloud** database `otel`.

## Cloud tables (queried during packaging)

| Table | Approx. rows | Role |
|---|---:|---|
| `otel.otel_logs` | ~12k+ | Log search source in HyperDX |
| `otel.otel_traces` | ~250k | Trace search source in HyperDX |
| `otel.otel_metrics_*` | present | Collector metrics pipeline |

Snapshot: [`otel_tables_summary.json`](./otel_tables_summary.json).

## HyperDX UI

Local HyperDX: `http://localhost:8080` (after `docker compose … up`).

Screenshots:

- [`hyperdx-team-data-sources.png`](./hyperdx-team-data-sources.png) — Team Settings → Data: **Logs → `otel.otel_logs`**, **Traces → `otel.otel_traces`**, connection **ClickHouse Cloud**
- [`hyperdx-search-otel-logs.png`](./hyperdx-search-otel-logs.png) — Search UI targeting `otel.otel_logs` (generated SQL visible)
- [`hyperdx-librechat-logs.png`](./hyperdx-librechat-logs.png) — Logs filtered `ServiceName:librechat` (LibreChat Winston → `librechat-log-shipper` → OTLP → HyperDX); MCP tool traffic visible

## Pipeline

```
LibreChat /app/logs  →  librechat-log-shipper (filelog)
RCA MCP / probes     →  OTLP :4318  →  ClickStack collector  →  Cloud DB otel
                                                              ↓
                                                         HyperDX reads CH
```

Compose sets `HYPERDX_OTEL_EXPORTER_CLICKHOUSE_DATABASE=otel` and default sources for logs/traces on those tables. OTLP ingest uses the HyperDX team API key (`authorization` header). LibreChat shipping: `source_code/stack/librechat-compose.yml` + `source_code/stack/otel/librechat-logs-collector.yml`.
