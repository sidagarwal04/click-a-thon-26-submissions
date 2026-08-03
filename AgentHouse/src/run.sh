#!/usr/bin/env bash
# FeatureMage / AgentHouse — local bootstrap + one-shot pipeline helpers.
# Usage (from this directory or AgentHouse/):
#   ./run.sh sync
#   ./run.sh init-db
#   ./run.sh api
#   ./run.sh instrument <feature_id>     # e.g. 01_express_checkout | unseen_data
#   ./run.sh health
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Prefer src/ when invoked from the submissions AgentHouse folder
if [[ -d "$ROOT/src" && -f "$ROOT/src/pyproject.toml" ]]; then
  ROOT="$ROOT/src"
elif [[ ! -f "$ROOT/pyproject.toml" && -f "$ROOT/../src/pyproject.toml" ]]; then
  ROOT="$(cd "$ROOT/../src" && pwd)"
fi

cd "$ROOT"

cmd="${1:-}"
shift || true

need_env() {
  if [[ ! -f .env ]]; then
    echo "Missing .env — copy from .env.example and fill ClickHouse / Postgres / API keys:"
    echo "  cp .env.example .env"
    exit 1
  fi
}

case "$cmd" in
  sync)
    uv sync
    uv sync --group dev
    ;;
  init-db)
    need_env
    uv run python -m instrumentation_agent.init_db
    if [[ -f context_agent/scripts/init_schema.py ]]; then
      uv run python context_agent/scripts/init_schema.py || true
    fi
    ;;
  api)
    need_env
    exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${AGENT_OS_PORT:-8000}"
    ;;
  instrument)
    need_env
    feature_id="${1:-}"
    if [[ -z "$feature_id" ]]; then
      echo "Usage: $0 instrument <feature_id>"
      exit 1
    fi
    port="${AGENT_OS_PORT:-8000}"
    curl -sS -X POST "http://127.0.0.1:${port}/v1/instrument" \
      -H 'content-type: application/json' \
      -d "{\"feature_id\":\"${feature_id}\"}"
    echo
    ;;
  health)
    port="${AGENT_OS_PORT:-8000}"
    curl -sS "http://127.0.0.1:${port}/health"
    echo
    ;;
  *)
    cat <<EOF
AgentHouse run helper (cwd: $ROOT)

  $0 sync                 # uv sync (+ dev)
  $0 init-db              # Postgres meta + context DDL
  $0 api                  # start FastAPI / AgentOS on :8000
  $0 instrument <id>      # POST /v1/instrument (API must be up)
  $0 health               # GET /health

See RUN.md for env vars and the full graded pipeline.
EOF
    exit 1
    ;;
esac
