# Click-a-thon 2026 · Atlys AgentHouse

Agentic analytics for Atlys: **feature `spec.md` + `events.ndjson` → structured metadata → ClickHouse schemas + Postgres registry → PM insights**. Three Agno agents are hosted on one **FastAPI** app (AgentOS). Instrumentation uses an [Agno Workflow](https://docs.agno.com/workflows/overview) on **Gemini**. Conversation follows Agno’s [SQLTools data-agent](https://docs.agno.com/use-cases/data-agents/querying-your-data) style. Traced with **Langfuse**.

---

## 1. Architecture

```
specs/*/spec.md + events.ndjson
base_context.md
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI  ── hosts ──►  Agno AgentOS                │
│    Instrumentation │ Context │ Conversation         │
│    (Workflow: load → summarize → plan pipeline)     │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
   ClickHouse Cloud              Postgres
   event fact tables             meta_features / meta_events
                                 context snapshots
                                 Agno session db*
           │                          │
           └────────────┬─────────────┘
                        ▼
              PM insights + Langfuse traces

* Session PostgresDb ≠ SQLTools warehouse engines ([Agno](https://docs.agno.com/use-cases/data-agents/querying-your-data))
```

| Layer | Docs | Runtime code |
|-------|------|----------------|
| **Instrumentation** | [`instrumentation_agent/`](./instrumentation_agent/) | routes, agent workflow, tools, interfaces, models, utils, db |
| **Context** | [`context_agent/`](./context_agent/) | (same pattern under `context_agent/`) |
| **Conversation** | [`conversation_agent/`](./conversation_agent/) | (same pattern under `conversation_agent/`) |

| Store | Owns |
|-------|------|
| **ClickHouse** | Event / funnel fact tables |
| **Postgres** | `meta_features`, `meta_events` (metadata registry), later context + sessions |

**Runtime:** FastAPI hosts Agno (`AgentOS(base_app=app)`). No sidecar.  
**LLM (Instrumentation):** Gemini via `GOOGLE_API_KEY` / `GEMINI_MODEL`.  
**Analytics SQL:** SQLTools + **SQLGlot** (`clickhouse`) on the Conversation path.  
**Out of scope:** auth, prod deploy, streaming ingest, polished UIs.

Layer detail lives in each folder’s `README.md` — keep this file as the map.

---

## 2. Repository structure

```
clickathon_2026_agenthouse/
├── README.md
├── pyproject.toml / uv.lock / .python-version
├── .env.example
├── app/
│   └── main.py                       ← thin FastAPI host (mounts agent routers)
├── instrumentation_agent/            ← Instrumentation package
│   ├── agent/orchestration.py        ← Agno Workflow (load → summarize → plan)
│   ├── routes/                       ← thin FastAPI routers
│   ├── interfaces/                   ← entrypoints used by routers/tools
│   ├── models/                       ← request/response + domain models
│   ├── db/                           ← CRUD (meta_features, meta_events)
│   ├── utils/                        ← profiler, paths, ClickHouse + SQLGlot
│   ├── tools/
│   │   ├── pipeline.py               ← mocked create/update/skip (step 2)
│   │   └── instrumentation.py        ← CH/PG apply toolkit (later)
│   ├── sql/postgres_meta_registry.sql
│   ├── settings.py
│   └── init_db.py
├── context_agent/                    ← layer design (+ code later)
├── conversation_agent/               ← layer design (+ code later)
├── tests/
│   ├── fixtures/                     ← sample feature packs for pytest
│   │   └── 01_express_checkout/      ← spec.md + events.ndjson
│   └── test_instrumentation_routes.py
└── .cursor/skills|rules/
```

---

## 3. Instrumentation workflow (current)

[`POST /v1/instrument`](./instrumentation_agent/README.md) runs this [Agno Workflow](https://docs.agno.com/workflows/overview):

1. **`load_spec`** — resolve `feature_id` / `dataset_path` / `spec_path`, read `spec.md`
2. **`summarize_spec`** — Gemini structured output → `FeatureSpecMetadata` (event metadata JSON)
3. **`plan_pipeline`** — use that JSON + mocked `PipelineTools` (`inspect` / `create` / `update` / `skip`) → `PipelinePlan`

Deterministic apply (`instrument_feature` → ClickHouse + Postgres) remains available via interfaces/tools for later wiring.

---

## 4. Local development (uv)

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed  
- Python **3.12+** (uv will fetch it if needed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if missing
```

### Sync environment

```bash
cd clickathon_2026_agenthouse
uv sync
uv sync --group dev    # pytest, ruff
```

### Configure secrets

```bash
cp .env.example .env
# edit .env — Postgres, ClickHouse, GOOGLE_API_KEY, GEMINI_MODEL, SPECS_ROOT, Langfuse
```

Never commit `.env`.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres metadata registry |
| `CLICKHOUSE_*` | ClickHouse Cloud event facts |
| `SPECS_ROOT` | Contest packs: `{SPECS_ROOT}/{feature_id}/spec.md` + `events.ndjson` |
| `GOOGLE_API_KEY` | Gemini for the Instrumentation workflow |
| `GEMINI_MODEL` | Default `gemini-2.5-flash` |

### Common commands

```bash
uv run pytest
uv run python -m instrumentation_agent.init_db
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Re-run **`uv sync`** after pulling when `pyproject.toml` / `uv.lock` change.

---

## 5. Testing when feature data is added

Every contest feature is a pack: **`spec.md` + `events.ndjson`**. When you add a new feature (or Day-2 unseen sixth), cover it with fixtures + pytest, then optionally hit the live workflow.

### 5.1 Add a feature fixture

```text
tests/fixtures/<feature_id>/
├── spec.md          # journey bullets (event names in backticks)
└── events.ndjson    # one JSON object per line; "event" field required
```

Example layout (already in repo): `tests/fixtures/01_express_checkout/`.

Contest packs under `SPECS_ROOT` use the same shape:

```text
{SPECS_ROOT}/02_some_feature/spec.md
{SPECS_ROOT}/02_some_feature/events.ndjson
```

### 5.2 Extend unit tests

In `tests/test_instrumentation_routes.py` (or a new `tests/test_<feature_id>.py`):

1. **Journey parse** — assert `parse_journey_order(spec)` matches the bullet order in `spec.md`.
2. **Profiler** — `profile_feature(feature_id, spec_path, events_path)` returns one table per event, columns only from NDJSON (no invented fields), sensible `row_count`.
3. **Path resolve** — `resolve_feature_paths(dataset_path=...)` finds `spec.md` + `events.ndjson`.
4. **HTTP (mocked LLM)** — `POST /v1/instrument` with `dataset_path` / `feature_id` still returns 200 when `run_instrumentation_agent` is patched (keeps CI free of Gemini calls).

```bash
# fast, no network / no Gemini
uv run pytest -q

# focus on instrumentation
uv run pytest tests/test_instrumentation_routes.py -q
```

### 5.3 Live smoke test (optional, needs `.env`)

With Postgres + ClickHouse + `GOOGLE_API_KEY` configured:

```bash
uv run python -m instrumentation_agent.init_db
uv run uvicorn app.main:app --reload --port 8000
```

**By fixture path** (good while developing a new pack):

```bash
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d "{\"dataset_path\":\"$(pwd)/tests/fixtures/01_express_checkout\"}" | jq .
```

**By contest `feature_id`** (uses `SPECS_ROOT`):

```bash
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"feature_id":"01_express_checkout"}' | jq .
```

Expect `spec_metadata` (structured journey JSON) and `pipeline_plan` (create/update/skip via mocked tools). Then:

```bash
curl -s localhost:8000/v1/registry/01_express_checkout | jq .
curl -s localhost:8000/health | jq .
```

### 5.4 Checklist for a new feature pack

- [ ] `spec.md` lists journey events in order (backticks)
- [ ] `events.ndjson` uses matching `"event"` names; nested fields flatten without invented columns
- [ ] Fixture copied under `tests/fixtures/<feature_id>/` (or pointed at via `dataset_path`)
- [ ] Profiler / journey assertions added and `uv run pytest` passes
- [ ] Optional: live `POST /v1/instrument` returns metadata + pipeline plan
- [ ] Day-2 sixth spec uses the **same** pipeline (no one-off scripts)

---

## 6. Stack

| Piece | Choice |
|-------|--------|
| Package / env | **uv** (`uv sync`) |
| Runtime | **FastAPI** hosts **Agno** (Workflow + AgentOS) |
| Instrumentation LLM | **Gemini** (`agno.models.google.Gemini`) |
| Query agent | Agno **`SQLTools`** ([docs](https://docs.agno.com/use-cases/data-agents/querying-your-data)) |
| Event store | **ClickHouse Cloud** |
| Metadata | **Postgres** (`meta_features`, `meta_events`) |
| SQL safety | **SQLGlot** (`clickhouse`) |
| Tracing | **Langfuse** |

---

## 7. Build order

1. Postgres `meta_*` + Instrumentation workflow (`instrumentation_agent/`) — **in progress**  
2. Wire real pipeline tools (replace mocks) → ClickHouse + Postgres apply  
3. Thin `app/main.py` + AgentOS exposure for Instrumentation  
4. Context agent package (same layout)  
5. Conversation SQLTools data agent  
6. Specs 01–05 E2E → Day-2 unseen sixth spec  

---

## 8. Evaluation

Schema quality · registry quality · actionable insights · context freshness · full Langfuse/Agno traces (Day-2 proof required).

---

## 9. References

| Doc | Purpose |
|-----|---------|
| [Agno Workflows](https://docs.agno.com/workflows/overview) | Instrumentation orchestration |
| [Agno: Querying your data](https://docs.agno.com/use-cases/data-agents/querying-your-data) | SQLTools data-agent pattern |
| [`instrumentation_agent/README.md`](./instrumentation_agent/README.md) | Instrumentation API + workflow steps |
| [`context_agent/README.md`](./context_agent/README.md) | Context design |
| [`conversation_agent/README.md`](./conversation_agent/README.md) | Conversation / SQLTools design |
| [`.cursor/skills/clickathon-agenthouse/SKILL.md`](./.cursor/skills/clickathon-agenthouse/SKILL.md) | Contest workflow |
| [`.cursor/rules/clickathon-stack.mdc`](./.cursor/rules/clickathon-stack.mdc) | Stack constraints |
