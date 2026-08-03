# RUN.md — FeatureMage / AgentHouse

End-to-end runbook for the Atlys track: Instrumentation → ClickHouse + Postgres context → Conversation / Visualization.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) and Python **3.12+**
- ClickHouse Cloud service (database `atlys`)
- Postgres (metadata registry + context catalog)
- API keys: `GOOGLE_API_KEY` (Instrumentation / Gemini), optionally `ANTHROPIC_API_KEY` (Conversation / Claude)
- Contest feature packs under `SPECS_ROOT` (`spec.md` + `events.ndjson` per feature)

## 1. Configure env

```bash
cd clickathon_2026_agenthouse
cp .env.example .env
```

Fill at least:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres — `meta_*` + `context_*` |
| `CLICKHOUSE_HOST` / `PORT` / `USER` / `PASSWORD` | ClickHouse Cloud (HTTPS `8443`, `CLICKHOUSE_SECURE=true`) |
| `CLICKHOUSE_DATABASE` | `atlys` |
| `SPECS_ROOT` | Path to Atlys packs (e.g. `../click-a-thon-2026/Atlys/specs` or include `unseen_data`) |
| `GOOGLE_API_KEY` / `GEMINI_MODEL` | Instrumentation LLM |
| `MODEL_PROVIDER` / `MODEL_ID` / `ANTHROPIC_API_KEY` | Conversation / Visualization |
| `LANGFUSE_*` | Tracing (public share links for graded runs) |

Never commit `.env`.

## 2. Install + init metadata

```bash
uv sync
uv sync --group dev
uv run python -m instrumentation_agent.init_db
# Context catalog DDL (if not already applied):
uv run python context_agent/scripts/init_schema.py
# Optional baseline context:
uv run python -m context_agent.seed_v0
```

## 3. One command — instrument a feature end to end

Start the API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then run Instrumentation (creates ClickHouse tables + MVs, registers `meta_*`, publishes a new context version):

```bash
# Known specs 01–05
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"feature_id":"01_express_checkout"}' | jq .

# Day-2 sixth spec (coupon / promo) — same pipeline
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d '{"feature_id":"unseen_data"}' | jq .
```

Or by pack path:

```bash
curl -s -X POST localhost:8000/v1/instrument \
  -H 'content-type: application/json' \
  -d "{\"dataset_path\":\"$SPECS_ROOT/unseen_data\"}" | jq .
```

Verify registry + health:

```bash
curl -s localhost:8000/v1/registry/unseen_data | jq .
curl -s localhost:8000/health | jq .
```

Optional: load NDJSON into the new tables / check activity MVs:

```bash
uv run python -m instrumentation_agent.verify_activity_mvs --feature-id unseen_data
```

## 4. Conversation / Visualization (Analytics)

```bash
# AgentOS visualization service (see conversation_agent README for port/env)
uv run python -m conversation_agent   # or the project's documented AgentOS entrypoint
```

LibreChat UI (if used): configure `frontend/librechat.yaml` against the Visualization endpoint, then start the LibreChat stack per `frontend/` docs. Point judges at the hosted demo URL in the submission README.

## 5. What “done” looks like for a graded run

1. ClickHouse: per-event tables + `mv_*_to_activity` → `activity_events`
2. Postgres: `meta_features` / `meta_events` updated; new `context_versions` row with `is_current=true`
3. Langfuse: trace for that Instrumentation (and Analytics) run — export JSON or public share link into the submissions `unseen_data/` folder
