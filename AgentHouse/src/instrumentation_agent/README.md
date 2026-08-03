# Instrumentation Agent

Turns a feature **`spec.md` + `events.ndjson`** into ClickHouse tables + Postgres metadata.

Parent overview: [`../README.md`](../README.md)

## Package layout

```
instrumentation_agent/
├── routes/                 # thin FastAPI routers
│   ├── health.py
│   └── instrumentation.py
├── interfaces/             # service entrypoints (not fat __init__)
│   ├── health.py
│   └── instrumentation.py
├── models/
│   ├── schemas.py          # Pydantic request/response
│   └── domain.py           # dataclasses
├── db/
│   ├── connection.py
│   ├── meta_features.py
│   └── meta_events.py
├── utils/                  # concrete helper modules only
│   ├── profiler.py
│   ├── paths.py
│   ├── clickhouse.py       # SQLGlot-validated CH SQL
│   └── serialize.py
├── agent/orchestration.py  # Agno Workflow (summarize → plan)
├── tools/
│   ├── instrumentation.py  # CH/PG apply toolkit (later steps)
│   └── pipeline.py         # mocked create/update/skip tools
├── sql/
├── settings.py
└── init_db.py
```

`__init__.py` files stay thin (re-exports or empty). Import from concrete modules.
Thin host: `app/main.py` mounts `instrumentation_agent.routes`.

## Layering

| Layer | Responsibility |
|-------|----------------|
| **routes** | HTTP only; call `interfaces` |
| **interfaces** | Orchestration (`instrument_feature`, `get_registry`, `health_check`) |
| **models** | Pydantic requests/responses + domain dataclasses |
| **db** | Table-scoped CRUD classes only |
| **utils** | Shared helpers; ClickHouse DDL/queries validated with **SQLGlot** |

## API

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/health` | Postgres + ClickHouse ping |
| `GET` | `/v1/registry/{feature_id}` | Read metadata |
| `POST` | `/v1/instrument` | Run **Agno Instrumentation workflow** on dataset + `spec.md` |

```bash
# By feature id under SPECS_ROOT
curl -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"feature_id":"01_express_checkout"}'

# By explicit dataset directory (events.ndjson + spec.md)
curl -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"dataset_path":"/path/to/01_express_checkout","spec_path":"/path/to/01_express_checkout/spec.md"}'
```

Workflow ([Agno Workflows](https://docs.agno.com/workflows/overview)) in `agent/orchestration.py`:

1. **`load_spec`** — resolve paths and read `spec.md`
2. **`summarize_spec`** — Gemini structured output → `FeatureSpecMetadata` (event metadata JSON)
3. **`plan_pipeline`** — use that JSON + mocked `PipelineTools` (`inspect` / `create` / `update` / `skip`) → `PipelinePlan`

## Testing new feature data

When a feature pack is added (`spec.md` + `events.ndjson`), follow the root guide:
[Testing when feature data is added](../README.md#5-testing-when-feature-data-is-added).

Short path:

```bash
# 1) Drop pack under tests/fixtures/<feature_id>/ (or use SPECS_ROOT)
# 2) Assert journey + profiler in tests/
uv run pytest tests/test_instrumentation_routes.py -q

# 3) Optional live workflow (needs GOOGLE_API_KEY)
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d "{\"dataset_path\":\"$(pwd)/tests/fixtures/01_express_checkout\"}"
```
