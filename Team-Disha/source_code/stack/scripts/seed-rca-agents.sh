#!/usr/bin/env bash
# Seed LibreChat agents via login + CSRF (best-effort).
# Prefer modelSpecs in librechat.yaml (already configured) — this is optional.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"
# shellcheck disable=SC1090
set -a; source <(grep -E '^(LIBRECHAT_|OPENAI_)' "$ENV_FILE" | tr -d '\r'); set +a

BASE="${LIBRECHAT_URL:-http://localhost:3080}"
EMAIL="${LIBRECHAT_USER_EMAIL:-admin@clickathon.local}"
PASS="${LIBRECHAT_USER_PASSWORD:-}"

if [[ -z "$PASS" ]]; then
  echo "Set LIBRECHAT_USER_PASSWORD in .env"
  exit 1
fi

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "Logging into LibreChat as $EMAIL ..."
LOGIN=$(curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")

TOKEN=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" <<<"$LOGIN" || true)
CSRF=$(grep -i csrftoken "$COOKIE_JAR" | awk '{print $NF}' | tail -1 || true)

if [[ -z "$TOKEN" ]]; then
  echo "Login failed. Create a user first (scripts/create-librechat-user.sh)."
  echo "$LOGIN" | head -c 400
  exit 1
fi

echo "Login OK. ModelSpecs in librechat.yaml already expose RCA agents."
echo "Open $BASE → select 'InMobi RCA Orchestrator' and attach MCP tools if prompted."
echo "Optional: create persisted agents in the Agent Builder using prompts in stack/agents/."
