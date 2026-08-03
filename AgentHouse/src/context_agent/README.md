# Context Agent (catalog library + read-only Agno agent)

Maintains the **living business context layer** in **Postgres** and exposes it as
deterministic tools. A **read-only Agno Context Agent** answers questions using
those tools (no publish).

Parent overview: [`../README.md`](../README.md) · Table design: [`TABLES.md`](./TABLES.md)

## Role

```
Instrumentation writes meta_features / meta_events → Postgres
Scripts / Instrumentation publish context_versions / context_items
        │
        ▼
  get_latest_context_items()   → meaning (context_*)
  get_feature_meta(feature_id) → journey + per-event ch_table + payload columns
  publish_context_version(...) → writers only (seed / Instrumentation)
        │
        ▼
  Context Agent (read-only)  ·  Conversation discover_schema
```

## Read-only Context Agent

```bash
uv run python -m context_agent \
  "What is the current context version and core pre-purchase funnel?"

uv run python -m context_agent \
  "Summarize the unseen_data coupon journey from feature meta"
```

Agent tools: `get_latest_context_items`, `get_feature_meta` via `get_context_read_tools()`.

## The catalog tools

| Tool | Purpose |
|------|---------|
| `get_latest_context_items` | Current `context_version` + `context_items` |
| `get_feature_meta(feature_id)` | `meta_features` + `meta_events` (Instrumentation) |
| `publish_context_version` | New version: copy-forward + upserts/deletes (not on Context Agent) |

```python
from context_agent import (
    get_context_catalog_tools,  # Agno Toolkit: read + publish
    get_context_read_tools,     # Agno Toolkit: read-only
    get_latest_context_items,
    get_feature_meta,
    publish_context_version,
    build_agent,
)

# Context Agent / Conversation discover:
tools = [get_context_read_tools()]  # or get_context_catalog_tools() when publish needed
```

`get_postgres_sql_tools()` is optional admin/debug only.

## Postgres tables

See [`TABLES.md`](./TABLES.md). Context DDL is only `context_*`; meta DDL lives under Instrumentation.

## Environment

Repo-root `.env`:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

`SESSION_DATABASE_URL` is only needed if some other agent uses Agno sessions against Postgres.

## Setup

```bash
uv sync
# Meta tables (Instrumentation):
uv run python -m instrumentation_agent.init_db
# Context tables (this package):
uv run python context_agent/scripts/init_schema.py
# Seed living context (entities, metrics, core funnel_steps):
uv run python context_agent/scripts/seed_v0.py

# Optional health check service (no agent):
PYTHONPATH=context_agent/src uv run uvicorn context_agent.app:app --reload --port 8001
```

Without `seed_v0`, `get_latest_context_items` returns empty and Conversation
`discover_schema` cannot invent schema (empty SchemaContext + notes).

## Related

- [`TABLES.md`](./TABLES.md)
- [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- [`../conversation_agent/README.md`](../conversation_agent/README.md)
