#!/usr/bin/env bash
# Start/stop the API (:8010) and the UI (:3100). Anything launched inside a
# Claude session dies with it — both halves use nohup so the servers survive
# the session that started them.
#
#   ./dev.sh              both
#   ./dev.sh start ui     just one
#   ./dev.sh stop         both
#   ./dev.sh status
#
# UI_MODE=preview serves the production build instead of the dev server. That
# needs a build, so the script runs one first; it takes ~10s, which is why
# `dev` is the default.
set -euo pipefail
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
API_PORT="${API_PORT:-8010}"
UI_PORT="${UI_PORT:-3100}"
UI_MODE="${UI_MODE:-dev}"
API_PID=".api.pid"
UI_PID=".ui.pid"

running() {  # $1 = pidfile
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

port_held() {  # $1 = port
  lsof -ti :"$1" >/dev/null 2>&1
}

start_api() {
  if running "$API_PID"; then
    echo "api  already running (pid $(cat $API_PID)) on :$API_PORT"; return 0
  fi
  nohup "$PY" -m uvicorn api.main:app --host 0.0.0.0 --port "$API_PORT" > api.log 2>&1 &
  echo $! > "$API_PID"
  sleep 2
  if running "$API_PID" && port_held "$API_PORT"; then
    echo "api  http://0.0.0.0:$API_PORT (pid $(cat $API_PID)) — api.log"
  else
    echo "api  FAILED — last lines of api.log:"; tail -5 api.log; return 1
  fi
}

start_ui() {
  if running "$UI_PID"; then
    echo "ui   already running (pid $(cat $UI_PID)) on :$UI_PORT"; return 0
  fi
  if [ ! -d ui/node_modules ]; then
    echo "ui   node_modules missing — run: (cd ui && npm install)"; return 1
  fi
  if [ "$UI_MODE" = "preview" ]; then
    echo "ui   building..."
    if ! (cd ui && npm run build) > ui-build.log 2>&1; then
      echo "ui   BUILD FAILED — see ui-build.log:"; tail -15 ui-build.log; return 1
    fi
  fi
  nohup npm --prefix ui run "$UI_MODE" > ui.log 2>&1 &
  echo $! > "$UI_PID"
  sleep 3
  # Check the port, not just the pid: vite.config sets strictPort, so a clash
  # is fatal to vite while the npm wrapper can linger long enough to look alive.
  if port_held "$UI_PORT"; then
    echo "ui   http://localhost:$UI_PORT ($UI_MODE, pid $(cat $UI_PID)) — ui.log"
  else
    echo "ui   FAILED to bind :$UI_PORT — last lines of ui.log:"; tail -8 ui.log; return 1
  fi
}

stop_one() {  # $1 = pidfile  $2 = port  $3 = label
  if [ -f "$1" ]; then
    pid=$(cat "$1")
    # Kill the process group: npm spawns vite as a child, and killing only the
    # npm wrapper leaves vite holding the port.
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    if [ -n "$pgid" ]; then kill -- "-$pgid" 2>/dev/null || true; else kill "$pid" 2>/dev/null || true; fi
    rm -f "$1"
    sleep 1
  fi
  # A half-dead worker holding the port is worse than a clean failure.
  if port_held "$2"; then
    lsof -ti :"$2" | xargs kill -9 2>/dev/null || true
  fi
  echo "$3   stopped"
}

status_one() {  # $1 = pidfile  $2 = port  $3 = label
  if running "$1" && port_held "$2"; then
    echo "$3   running (pid $(cat $1)) on :$2"
  elif port_held "$2"; then
    echo "$3   :$2 held by an untracked process (pid $(lsof -ti :$2 | tr '\n' ' '))"
  else
    echo "$3   not running"
  fi
}

cmd="${1:-start}"
what="${2:-both}"
case "$what" in both|api|ui) ;; *) echo "unknown target '$what' — use api, ui or both"; exit 1 ;; esac

rc=0
case "$cmd" in
  start)
    if [ "$what" = both ] || [ "$what" = api ]; then start_api || rc=1; fi
    if [ "$what" = both ] || [ "$what" = ui  ]; then start_ui  || rc=1; fi
    ;;
  stop)
    if [ "$what" = both ] || [ "$what" = ui  ]; then stop_one "$UI_PID"  "$UI_PORT"  "ui"; fi
    if [ "$what" = both ] || [ "$what" = api ]; then stop_one "$API_PID" "$API_PORT" "api"; fi
    ;;
  restart)
    "$0" stop "$what"; "$0" start "$what" || rc=1
    ;;
  status)
    status_one "$API_PID" "$API_PORT" "api"
    status_one "$UI_PID"  "$UI_PORT"  "ui"
    ;;
  *) echo "usage: $0 {start|stop|restart|status} [api|ui|both]"; exit 1 ;;
esac
exit $rc
