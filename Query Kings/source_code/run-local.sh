#!/usr/bin/env bash
# One-command local pipeline: Docker → setup → (optional) all specs → serve
#
# Usage (from source_code/):
#   ./run-local.sh              # setup + instrument 6 specs (5 known + unseen) + serve
#   ./run-local.sh --setup-only # Docker + pnpm cli setup only
#   ./run-local.sh --no-serve   # setup + specs, don't start the UI
#
# Platforms: macOS, Linux, Windows via WSL2 only (not PowerShell/CMD).
# Prerequisites: Docker, Node 22+, pnpm, and backend/.env filled
# (see ../RUN.md and ../README.md).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
COMPOSE=(docker compose)
SETUP_ONLY=0
NO_SERVE=0
MIN_NODE_MAJOR=22

for arg in "$@"; do
  case "$arg" in
    --setup-only) SETUP_ONLY=1 ;;
    --no-serve) NO_SERVE=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

fail() {
  echo "✗ $*" >&2
  exit 1
}

ok() {
  echo "✓ $*"
}

echo "==> Checking prerequisites"

# Native Windows shells cannot run this script.
uname_s="$(uname -s 2>/dev/null || echo unknown)"
if [[ "$uname_s" == MINGW* || "$uname_s" == MSYS* || "$uname_s" == CYGWIN* ]]; then
  fail "Native Windows (Git Bash / MSYS) is not supported for local setup.
  Use WSL2 (Ubuntu recommended), install Docker Desktop with WSL integration,
  then run this script from inside WSL:
    cd source_code && ./run-local.sh"
fi

if [[ -n "${WINDIR:-}" && -z "${WSL_DISTRO_NAME:-}" && "$uname_s" != Linux && "$uname_s" != Darwin ]]; then
  fail "Native Windows detected. Use WSL2 — PowerShell/CMD will not work."
fi

if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
  ok "WSL2 ($WSL_DISTRO_NAME)"
elif [[ "$uname_s" == Darwin ]]; then
  ok "macOS"
elif [[ "$uname_s" == Linux ]]; then
  ok "Linux"
else
  ok "OS: $uname_s"
fi

command -v docker >/dev/null 2>&1 || fail "Docker is required.
  Install Docker Desktop (macOS/Windows) or Docker Engine (Linux), start it, retry."

docker info >/dev/null 2>&1 || fail "Docker daemon is not running.
  Open Docker Desktop (or start the docker service) and retry."

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
  ok "Docker Compose (plugin)"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
  ok "docker-compose (legacy)"
else
  fail "Docker Compose is required (docker compose …)."
fi

command -v node >/dev/null 2>&1 || fail "Node.js is required.
  Install Node 22+ from https://nodejs.org/ (macOS: brew install node)."

node_major="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)"
if [[ "$node_major" -lt "$MIN_NODE_MAJOR" ]]; then
  fail "Node.js $MIN_NODE_MAJOR+ required (found $(node --version))."
fi
ok "Node $(node --version)"

command -v pnpm >/dev/null 2>&1 || fail "pnpm is required.
  Install with: npm install -g pnpm"

ok "pnpm $(pnpm --version)"

if [[ ! -f "$BACKEND/.env" ]]; then
  fail "Missing backend/.env
  cp backend/.env.example backend/.env
  Then set GROQ_API_KEY and LANGFUSE_* (start Langfuse once to create a project)."
fi
ok "backend/.env present"

env_val() {
  # Read KEY=value from .env (first match); strips quotes.
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$BACKEND/.env" | head -n1 || true)"
  line="${line#*=}"
  line="${line%\"}"
  line="${line#\"}"
  line="${line%\'}"
  line="${line#\'}"
  printf '%s' "$line"
}

groq_key="$(env_val GROQ_API_KEY)"
if [[ -z "$groq_key" || "$groq_key" == "gsk-your-groq-key" ]]; then
  fail "Set a real GROQ_API_KEY in backend/.env"
fi
ok "GROQ_API_KEY set"

for key in LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY LANGFUSE_BASE_URL LANGFUSE_PROJECT_ID; do
  val="$(env_val "$key")"
  if [[ -z "$val" || "$val" == *"your-langfuse"* || "$val" == "pk-lf-your-public-key" || "$val" == "sk-lf-your-secret-key" || "$val" == "your-langfuse-project-id" ]]; then
    fail "Set $key in backend/.env — for local Docker, copy values from backend/.env.example (they match compose LANGFUSE_INIT_*)."
  fi
done
ok "LANGFUSE_* set"

ch_url="$(env_val CLICKHOUSE_URL)"
if [[ -z "$ch_url" ]]; then
  fail "Set CLICKHOUSE_URL in backend/.env (local default: http://localhost:8123)"
fi
ok "CLICKHOUSE_URL=$ch_url"

echo "==> Prerequisites OK"
echo ""

echo "==> Starting ClickHouse + Langfuse"
"${COMPOSE[@]}" up -d clickhouse
"${COMPOSE[@]}" --profile langfuse up -d

echo "==> Waiting for ClickHouse"
for i in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T clickhouse clickhouse-client \
    --user schema_kings \
    --password schema_kings \
    --query 'SELECT 1' >/dev/null 2>&1; then
    break
  fi
  if [[ "$i" -eq 60 ]]; then
    fail "ClickHouse did not become ready in time."
  fi
  sleep 2
done
ok "ClickHouse ready"

echo "==> Waiting for Langfuse (http://localhost:3000)"
for i in $(seq 1 60); do
  if curl -fsS "http://localhost:3000/api/public/health" >/dev/null 2>&1 \
    || curl -fsS "http://localhost:3000/" >/dev/null 2>&1; then
    break
  fi
  if [[ "$i" -eq 60 ]]; then
    echo "⚠ Langfuse not healthy yet — continuing anyway (traces may fail until it is up)"
    break
  fi
  sleep 2
done
if curl -fsS "http://localhost:3000/api/public/health" >/dev/null 2>&1 \
  || curl -fsS "http://localhost:3000/" >/dev/null 2>&1; then
  ok "Langfuse reachable"
fi

echo "==> Installing backend deps"
(
  cd "$BACKEND"
  pnpm install
)

echo "==> pnpm cli setup (base tables + context)"
(
  cd "$BACKEND"
  pnpm cli setup
)

if [[ "$SETUP_ONLY" -eq 1 ]]; then
  echo ""
  echo "Setup complete."
  echo "  Langfuse:   http://localhost:3000"
  echo "  ClickHouse: http://localhost:8123"
  echo "Next: pnpm cli run ../specs/01_express_checkout   (from backend/)"
  exit 0
fi

echo "==> Instrumenting specs (5 known + 6th unseen)"
SPECS=(
  01_express_checkout
  02_group_family
  03_status_sharing
  04_abandoned_checkout_recovery
  05_instant_forex
  06_promo_coupon_checkout
)
(
  cd "$BACKEND"
  for spec in "${SPECS[@]}"; do
    echo "---- cli run ../specs/$spec"
    pnpm cli run "../specs/$spec"
  done
)

if [[ "$NO_SERVE" -eq 1 ]]; then
  echo ""
  echo "Pipeline complete. Start UI with: cd backend && pnpm cli serve"
  exit 0
fi

echo "==> Starting report UI (Ctrl+C to stop)"
echo "  http://127.0.0.1:8787"
cd "$BACKEND"
exec pnpm cli serve
