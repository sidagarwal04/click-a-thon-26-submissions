# Conversation Agent (Visualization)

NL analytics workflow: **question → schema → viz plan → SQL+execute**.  
Primary path: **template builders + clickhouse-connect**.  
Fallback: **LLM `generate_query` + ClickHouse MCP** (previous behaviour).

LibreChat chart UI uses a separate **metadata + data-plane** contract (below).

Parent overview: [`../README.md`](../README.md).

## LibreChat analytics API

Mounted on the shared host (`uvicorn app.main:app --port 8000`).

| Endpoint | Role |
|----------|------|
| `POST /api/analytics/query` | Prompt → metadata-only blocks (`Trend` / `Ranking` / `Pivot` / `Funnel`) |
| `POST /api/analytics/data` | Insight config → chart series / matrix (`trend` / `contributor` / `pivot`) |
| `POST /api/analytics/dimensions` | Dimension key → ordered member values |
| `POST /v1/analytics/run` | Internal structured analytics → `ExecuteResult` |

Blocks never embed chart points. The client loads points via `/data` and members via `/dimensions`. Only `/dimensions` uses a process-local TTL cache (`ANALYTICS_CACHE_TTL_SECONDS`, default 300). Responses include `latency_ms` (wall clock; cached dimension entries keep the original CH latency).

### Examples

```bash
# Part 1 — prompt → blocks
curl -s http://localhost:8000/api/analytics/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Show revenue trend monthly and a pivot by country and channel"}'

# Part 2a — trend series
curl -s http://localhost:8000/api/analytics/data \
  -H 'Content-Type: application/json' \
  -d '{
    "insight_type": "trend",
    "payload": {
      "fromtime": "2026-01-01",
      "totime": "2026-06-30",
      "metric_name": "revenue",
      "timegrain": "month",
      "filters": []
    }
  }'

# Part 2b — dimension members
curl -s http://localhost:8000/api/analytics/dimensions \
  -H 'Content-Type: application/json' \
  -d '{
    "dimension": "country",
    "fromtime": "2026-01-01",
    "totime": "2026-06-30",
    "metric_name": "revenue"
  }'
```

### Agno tools

```python
from conversation_agent.tools import get_analytics_tools

tools = [get_analytics_tools()]
# fetch_dimension_values(dimension="country", fromtime=..., totime=...)
# fetch_insight_data(insight_type="trend", fromtime=..., totime=..., metric_name="revenue")
# list_dimensions() / list_metrics()
# run_analytics(kind="funnel", event_names="a,b,c", dimensions="device_type")
```

Catalog aliases: `country` → `geoip_country_code`, `channel` → `device_type`.  
Metrics include `revenue`, `users`, `events`, `purchases`, funnel stage `*_users`, `conversion_rate`.

## Pipeline (CLI / AgentOS)

```
User question
      │
      ▼
┌─────────────────┐
│ discover_schema │  context catalog tools + SAS shape
│                 │  (activity_events envelope + payload)
│                 │  → SchemaContext   (LLM)
└────────┬────────┘
         ▼
┌─────────────────┐
│ plan_visualization │  SchemaContext → VizSpec          (LLM)
└────────┬────────┘
         ▼
┌─────────────────────────────────────────────────────┐
│ run_analytics                                        │
│  1) VizSpec → AnalyticsPlan → SQL template           │
│  2) SQLGlot validate → clickhouse-connect execute    │
│  else → LLM QuerySpec + MCP run_query (fallback)     │
└─────────────────────────────────────────────────────┘
```

## Deterministic builders (`query_builders.py`)

| `kind` | SQL pattern |
|--------|-------------|
| `funnel` | `windowFunnel` on `atlys.activity_events` (`event_name`) |
| `timeseries` | daily `count` / `uniqExact` by `event_name` |
| `breakdown` / `top_n` | `GROUP BY` envelope segment |
| `metric` | counts or rate (`event_names` = numerator,denominator) |
| `comparison` | current vs previous half-window |

Unsupported / invalid plans fall back to LLM + MCP.

## Layout

```
conversation_agent/
├── analytics.py              # run_analytics() orchestration
├── catalog.py                # metric/dimension wire keys → CH
├── cache.py                  # TTL cache for /dimensions only
├── data_plane.py             # trend/contributor/pivot + dimensions
├── query_planner.py          # prompt → AnalyticsQueryResponse
├── clickhouse_client.py      # SQLGlot + clickhouse-connect
├── query_builders.py         # AnalyticsPlan + SQL templates
├── tools.py                  # Agno Toolkit
├── routes/                   # FastAPI LibreChat + /v1/analytics/run
├── visualization_agent.py    # workflow + CLI / AgentOS
└── …
```

## Setup / run

Use the **`clickathon`** pyenv venv (not system `pip`).

```bash
pyenv activate clickathon   # or: PYENV_VERSION=clickathon
# Build SAS fact table from existing per-event CH tables (once):
python conversation_agent/scripts/build_activity_events.py --drop
python -m conversation_agent.visualization_agent "conversion by device last 30 days"
python -m conversation_agent.visualization_agent --os
```

`--sample N` loads at most N rows per source table for a quick smoke test.

```bash
uvicorn app.main:app --reload --port 8000
```

## Related

- Instrumentation: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Context: [`../context_agent/README.md`](../context_agent/README.md)
