#!/usr/bin/env bash
# One-command demo bring-up for RootCauseOS. Idempotent — safe to re-run.
#
#   ./scripts/demo_up.sh                       # seen dataset (rca.events + fixtures)
#   RCOS_TABLE=rca_e2e.ad_events \
#   RCOS_SCAN_BUNDLE=/path/scan.json ./scripts/demo_up.sh   # any new dataset
#
# Requires: the repo venv (or streamlit on PATH), docker (colima) for LibreChat.
set -u
cd "$(dirname "$0")/.."

VENV="${RCOS_VENV:-/private/tmp/claude-501/-Users-namangoyal/03386cf4-0670-46b5-a3d1-632295314c5d/scratchpad/clickathon/.venv}"
PY="$VENV/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

echo "── RootCauseOS demo up ──────────────────────────────"

# 1. LibreChat (docker) — start only if not already up
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q rcos-librechat; then
  echo "• starting LibreChat + Mongo (docker compose)…"
  docker compose -f integrations/librechat/docker-compose.yml up -d
else
  echo "• LibreChat containers already up"
fi

# 2. ClickStack / HyperDX (docker) — start only if not already up.
#    Own bundled ClickHouse; never the graded service. Spans need CLICKSTACK_ENABLED=1.
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q rcos-clickstack; then
  echo "• starting ClickStack (HyperDX :8081, OTLP :4318)…"
  docker compose -f integrations/clickstack/docker-compose.yml up -d
else
  echo "• ClickStack container already up"
fi

# 3. Shim (:8601) — restart for a clean slate
pkill -f integrations/openai_shim.py 2>/dev/null && sleep 1
nohup "$PY" integrations/openai_shim.py > /tmp/rcos-shim.log 2>&1 &
echo "• shim starting on :8601 (log /tmp/rcos-shim.log)"

# 4. Console (:8533) — restart, inheriting any RCOS_* env overrides
pkill -f "streamlit run ui/app.py" 2>/dev/null && sleep 1
nohup "$PY" -m streamlit run ui/app.py --server.port 8533 \
      --server.headless true > /tmp/rcos-app.log 2>&1 &
echo "• console starting on :8533 (log /tmp/rcos-app.log)"

# 5. Health — poll each service; --noproxy: corporate/system proxies must not
#    intercept localhost (a proxy here once faked a full outage)
sleep 6
ok=0
for spec in "8533 console" "8601/v1/models shim" "3080 librechat" "11434 ollama" "8081 clickstack"; do
  port="${spec%% *}"; name="${spec##* }"
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" -m 6 "http://127.0.0.1:${port}" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "  ✓ ${name} :${port%%/*}"
    ok=$((ok+1))
  else
    echo "  ✗ ${name} :${port%%/*} (http ${code:-none})"
  fi
done

echo "─────────────────────────────────────────────────────"
echo "console   → http://localhost:8533"
echo "librechat → http://localhost:3080"
echo "clickstack → http://localhost:8081"
[ -n "${RCOS_TABLE:-}" ]       && echo "table     → ${RCOS_TABLE}"
[ -n "${RCOS_SCAN_BUNDLE:-}" ] && echo "scan      → ${RCOS_SCAN_BUNDLE}"
[ -n "${RCOS_BUNDLE:-}" ]      && echo "bundle    → ${RCOS_BUNDLE}"
if [ "$ok" -lt 3 ]; then
  echo "⚠ fewer than 3 services healthy — check the logs above"
  exit 1
fi
