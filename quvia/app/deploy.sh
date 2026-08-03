#!/usr/bin/env bash
# One-click deployment: brings up all three stacks this project depends on —
# Langfuse (tracing), LibreChat (chat + MCP), and this dashboard (UI +
# ClickHouse MCP server). Safe to re-run; every step is idempotent
# (`docker compose up -d` no-ops on anything already running/up to date).
#
# Usage: ./deploy.sh
set -euo pipefail

# --- Paths to the three project directories on this machine -----------------
DASHBOARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANGFUSE_DIR="${LANGFUSE_DIR:-/Users/ganeshelango/Data/git/langfuse/langfuse}"
LIBRECHAT_DIR="${LIBRECHAT_DIR:-/Users/ganeshelango/Data/git/librechat/LibreChat/LibreChat}"

# LibreChat's docker-compose.yml runs its api container as "${UID}:${GID}" —
# leaving these unset makes Compose fall back to blank (root), which can
# leave bind-mounted files (data-node, uploads, logs) owned by root instead
# of you. UID is a read-only special variable in bash, so it can't be
# exported directly — HOST_UID/HOST_GID are passed to `docker compose`
# invocations via `env` instead (see run_compose below).
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

run_compose() {
  # Runs `docker compose "$@"` with UID/GID injected into that child
  # process's environment only, working around bash's readonly UID.
  env UID="$HOST_UID" GID="$HOST_GID" docker compose "$@"
}

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
fail() { printf '\033[1;31mxx\033[0m %s\n' "$1"; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker is not installed / not on PATH."
docker info >/dev/null 2>&1 || fail "Docker daemon isn't running — start Docker Desktop and re-run."

# --- Wait for an HTTP endpoint to respond (any status code = server is up) --
# Exit code 28 (curl's own timeout) counts as "up" too — SSE/streaming
# endpoints (like the ClickHouse MCP server) never close the connection on
# their own, so curl always hits --max-time on a healthy one. Only a real
# connection failure (e.g. exit 7, connection refused) means "not up yet".
wait_for() {
  local url="$1" name="$2" tries=60 ec
  printf '   waiting for %s' "$name"
  while [ "$tries" -gt 0 ]; do
    curl -s -o /dev/null --max-time 2 "$url"; ec=$?
    if [ "$ec" -eq 0 ] || [ "$ec" -eq 28 ]; then
      echo " ✓"
      return 0
    fi
    printf '.'
    sleep 2
    tries=$((tries - 1))
  done
  echo ""
  warn "$name didn't respond at $url within the timeout — check its logs."
  return 1
}

# --- 1. Langfuse (tracing) ---------------------------------------------------
if [ -d "$LANGFUSE_DIR" ]; then
  log "Starting Langfuse ($LANGFUSE_DIR)"
  (cd "$LANGFUSE_DIR" && run_compose up -d)
  wait_for "http://localhost:3000" "Langfuse" || true
else
  warn "Langfuse directory not found at $LANGFUSE_DIR — skipping. Set LANGFUSE_DIR to override."
fi

# --- 2. LibreChat (chat + MCP host) -----------------------------------------
if [ -d "$LIBRECHAT_DIR" ]; then
  log "Starting LibreChat ($LIBRECHAT_DIR)"
  # Excludes LibreChat's own "admin-panel" service — it binds port 3000,
  # which collides with Langfuse's web UI on the same port. Not needed for
  # the auto-login / MCP / default-model integration this project uses.
  (cd "$LIBRECHAT_DIR" && run_compose up -d api mongodb meilisearch vectordb rag_api)
  wait_for "http://localhost:3080" "LibreChat" || true
else
  warn "LibreChat directory not found at $LIBRECHAT_DIR — skipping. Set LIBRECHAT_DIR to override."
fi

# --- 3. This dashboard (UI + backend + ClickHouse MCP server) ---------------
log "Building and starting the dashboard ($DASHBOARD_DIR)"
[ -f "$DASHBOARD_DIR/.env" ] || fail ".env not found in $DASHBOARD_DIR — copy .env.example (if present) and fill in credentials first."
(cd "$DASHBOARD_DIR" && run_compose up -d --build)
wait_for "http://localhost:8000/api/health" "Dashboard" || true
wait_for "http://localhost:8001/sse" "ClickHouse MCP server" || true

log "Done."
cat <<EOF

  Dashboard    http://localhost:8000
  LibreChat    http://localhost:3080
  Langfuse     http://localhost:3000

If any service above didn't respond, check its logs with:
  (cd <its-directory> && docker compose logs -f)
EOF
