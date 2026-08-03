# ClickStack for RootCauseOS

ClickStack (OpenTelemetry -> HyperDX) is the observability leg. It stores its telemetry
in ClickHouse tables, so our traces JOIN against our own SQL in one statement.

## Start

    docker compose -f integrations/clickstack/docker-compose.yml up -d

| Port | Use |
|---|---|
| 8081 → 8080 | HyperDX UI — `CLICKSTACK_URL=http://localhost:8081` (host 8080 is taken by Tailscale on this machine) |
| 4317 | OTLP gRPC |
| 4318 | OTLP HTTP — `CLICKSTACK_OTLP` |

Instrumentation stays off until you set `CLICKSTACK_ENABLED=1`.

## Guardrail

This container uses its OWN bundled ClickHouse. Never give it the `CLICKHOUSE_*`
credentials (host, user, password) from the repo `.env` — it then writes `otel_*`
tables into the graded competition database. The compose file therefore has no
`env_file:` and no `${CLICKHOUSE_*}` interpolation.

## The demo claim (one SQL statement)

    docker exec rcos-clickstack clickhouse-client --query "
    SELECT t.SpanName,
           t.SpanAttributes['db.query_id'] AS query_id,
           round(t.Duration / 1e6, 1)      AS ms,
           count(l.TraceId)                AS log_lines
    FROM default.otel_traces AS t
    LEFT JOIN default.otel_logs AS l ON l.TraceId = t.TraceId
    WHERE t.ServiceName = 'rca-engine'
    GROUP BY 1, 2, 3 ORDER BY ms DESC LIMIT 10"
