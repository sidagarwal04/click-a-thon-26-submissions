# RUN.md — FeatureMage / AgentHouse

Source lives in [`src/`](./src/) (synced from the AgentHouse code repo).  
Shell helper: [`run.sh`](./run.sh).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) and Python **3.12+**
- ClickHouse Cloud (database `atlys`)
- Postgres (metadata registry + context catalog)
- `GOOGLE_API_KEY` (Instrumentation / Gemini); optional `ANTHROPIC_API_KEY` (Conversation)
- Contest packs on `SPECS_ROOT` (`spec.md` + `events.ndjson`)

## 1. Configure

```bash
cd AgentHouse/src
cp .env.example .env
# edit .env — DATABASE_URL, CLICKHOUSE_*, SPECS_ROOT, LLM + Langfuse keys
```

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres — `meta_*` + `context_*` |
| `CLICKHOUSE_HOST` / `PORT` / `USER` / `PASSWORD` | ClickHouse Cloud (`8443`, `SECURE=true`) |
| `CLICKHOUSE_DATABASE` | `atlys` |
| `SPECS_ROOT` | Path to Atlys feature packs (include `unseen_data` for the 6th spec) |
| `GOOGLE_API_KEY` / `GEMINI_MODEL` | Instrumentation |
| `MODEL_PROVIDER` / `MODEL_ID` / `ANTHROPIC_API_KEY` | Conversation / Visualization |
| `LANGFUSE_*` | Tracing |

## 2. Install + init

From `AgentHouse/`:

```bash
chmod +x run.sh
./run.sh sync
./run.sh init-db
```

Or manually:

```bash
cd src
uv sync && uv sync --group dev
uv run python -m instrumentation_agent.init_db
uv run python context_agent/scripts/init_schema.py
```

## 3. One command — instrument end to end

```bash
# terminal A
./run.sh api

# terminal B — known specs
./run.sh instrument 01_express_checkout

# Day-2 sixth spec (same pipeline)
./run.sh instrument unseen_data

./run.sh health
```

Equivalent curl:

```bash
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"feature_id":"unseen_data"}' | jq .
```

## 4. Graded outputs

After a successful instrument run you should have:

1. ClickHouse per-event tables + `mv_*_to_activity` → `activity_events`
2. Postgres `meta_*` + new `context_versions` (`is_current=true`)
3. Langfuse trace — export JSON / share link into `traces/`

Artifacts already in this submission folder: `unseen_data/`, `analytics/`, `Architecture.md`.
