#!/usr/bin/env bash
# Bring the demo up. Thin wrapper over docker compose -- the compose file is
# the source of truth; this exists to fail fast on credentials and to print the
# URLs, because `docker compose up` does neither.
#
#   scripts/start.sh          start everything (builds on first run)
#   scripts/start.sh stop     stop, keeping telemetry
#   scripts/start.sh status   what is up
#   scripts/start.sh logs     follow all logs
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-start}" in
  stop)   docker compose down; echo "stopped. Telemetry volumes kept — 'docker compose down -v' wipes them." ;;
  logs)   docker compose logs -f ;;
  status)
    docker compose ps --format '  {{.Service}}\t{{.Status}}'
    echo -n "  receivers  "
    docker exec trueccu-clickstack sh -c "netstat -tln 2>/dev/null | grep -qE ':(4317|4318) '" \
      && echo "OTLP up" || echo "NOT configured — finish setup at http://localhost:8081"
    ;;
  start)
    [[ -f .env.local ]] || { echo "missing .env.local — see CLAUDE_RUNBOOK.md step 1" >&2; exit 1; }
    # Fail on credentials now, not halfway through a demo.
    echo -n "checking ClickHouse Cloud ... "
    [[ "$(scripts/ch 'SELECT 1' 2>/dev/null | tr -d '[:space:]')" == "1" ]] \
      && echo ok || { echo "FAILED — check CH_* in .env.local"; exit 1; }

    docker compose up -d --build
    echo -n "waiting for the API ... "
    for _ in $(seq 1 40); do
      PEAK=$(curl -s "http://localhost:8787/api/summary" 2>/dev/null | sed -n 's/.*"peak_ccu":\([0-9]*\).*/\1/p')
      [[ -n "${PEAK:-}" ]] && break; sleep 2
    done
    echo "${PEAK:-no answer}"

    cat <<TXT

  dashboard   http://localhost:5173
  API         http://localhost:8787/api/summary
  HyperDX     http://localhost:8081     (source dropdown: Logs -> Traces)

  sanity      peak_ccu = ${PEAK:-<none>}   (expect 2882 on the provided data)
  logs        docker compose logs -f api

TXT
    ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
