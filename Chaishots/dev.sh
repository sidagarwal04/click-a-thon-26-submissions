#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\n[asklys] %s\n' "$*"
}

cleanup() {
  trap - EXIT INT TERM
  log "Stopping frontend and backend..."
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  [[ -z "$FRONTEND_PID" ]] || wait "$FRONTEND_PID" 2>/dev/null || true
  [[ -z "$BACKEND_PID" ]] || wait "$BACKEND_PID" 2>/dev/null || true
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[asklys] Missing required command: %s\n' "$1" >&2
    printf '[asklys] Install it, then rerun ./dev.sh\n' >&2
    exit 1
  fi
}

check_port() {
  local port="$1"
  local service="$2"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    printf '[asklys] Port %s is already in use; cannot start %s.\n' "$port" "$service" >&2
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 || true
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local service="$2"
  local pid="$3"
  local attempts=40
  local attempt=1

  while (( attempt <= attempts )); do
    if ! kill -0 "$pid" 2>/dev/null; then
      printf '[asklys] %s exited before becoming ready.\n' "$service" >&2
      return 1
    fi
    if curl --fail --silent --show-error --max-time 1 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
    ((attempt += 1))
  done

  printf '[asklys] Timed out waiting for %s at %s\n' "$service" "$url" >&2
  return 1
}

trap cleanup EXIT INT TERM

require_command uv
require_command npm
require_command curl
require_command lsof

check_port "$BACKEND_PORT" "backend"
check_port "$FRONTEND_PORT" "frontend"

if [[ ! -f "$PROJECT_DIR/.env" && ! -f "$PROJECT_DIR/.env.local" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env.local"
  log "Created .env.local from .env.example. Add service credentials when you need agent or ClickHouse operations."
fi

log "Checking Python dependencies..."
uv sync --project "$PROJECT_DIR/backend" --locked

if [[ ! -d "$FRONTEND_DIR/node_modules" ]] \
  || [[ ! -f "$FRONTEND_DIR/node_modules/.package-lock.json" ]] \
  || [[ "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_DIR/node_modules/.package-lock.json" ]]; then
  log "Installing frontend dependencies..."
  npm --prefix "$FRONTEND_DIR" ci
else
  log "Frontend dependencies are already installed."
fi

log "Starting backend on http://127.0.0.1:$BACKEND_PORT ..."
uv run --project "$PROJECT_DIR/backend" uvicorn app.main:app \
  --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

wait_for_url \
  "http://127.0.0.1:$BACKEND_PORT/api/v1/utils/health-check/" \
  "backend" \
  "$BACKEND_PID"

log "Starting frontend on http://127.0.0.1:$FRONTEND_PORT ..."
VITE_API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" \
  npm --prefix "$FRONTEND_DIR" run dev -- \
  --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!

wait_for_url "http://127.0.0.1:$FRONTEND_PORT" "frontend" "$FRONTEND_PID"
wait_for_url \
  "http://127.0.0.1:$FRONTEND_PORT/api/v1/utils/health-check/" \
  "frontend-to-backend proxy" \
  "$FRONTEND_PID"

log "Asklys is ready: http://127.0.0.1:$FRONTEND_PORT"
printf '[asklys] API docs: http://127.0.0.1:%s/docs\n' "$BACKEND_PORT"
printf '[asklys] Press Ctrl+C to stop both services.\n\n'

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  printf '[asklys] Backend stopped unexpectedly.\n' >&2
else
  printf '[asklys] Frontend stopped unexpectedly.\n' >&2
fi
exit 1
