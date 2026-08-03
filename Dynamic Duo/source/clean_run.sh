#!/usr/bin/env bash
# Fresh INGEST-ONLY run. Investigation is a separate step (./investigate.sh) so you
# control when it fires and over which timeline.
#
#   1. wipe                                 (docker compose down -v)
#   2. boot clickhouse + hyperdx + collector + seed
#   3. load seen data (+ unseen, if --unseen-dir given: its dims replace the old ones)
#   4. YOU: complete the HyperDX wizard     (the one paste-credentials moment)
#   5. auto: wire the team API key          (wire_traces.sh) + wait for the receiver
#   6. boot the rest (LibreChat + MCP)
#   THEN: ./investigate.sh                  (profiler + sweep + prefill, per dataset)
#
#   ./clean_run.sh --yes                                    # seen data only
#   ./clean_run.sh --yes --unseen-dir /path/to/unseen_data  # seen + unseen slice
#   DATA_DIR=/path ./clean_run.sh   or   ./clean_run.sh --data-dir /path
set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="${DATA_DIR:-../click-a-thon-2026/InMobi/data}"
UNSEEN_DIR=""
YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)        YES=1; shift ;;
    --data-dir)   DATA_DIR="$2"; shift 2 ;;
    --unseen-dir) UNSEEN_DIR="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ $YES -eq 0 ]]; then
  read -r -p "This WIPES all stack data (docker compose down -v). Continue? [y/N] " a
  [[ "$a" == "y" || "$a" == "Y" ]] || exit 0
fi

echo "== 0 · clearing the decks"
docker rm -f clickstack 2>/dev/null || true          # old exploration all-in-one, if present
( cd librechat && docker compose down -v --remove-orphans )
rm -rf .chlocal

# ports 8123/9000 must be free for the stack's clickhouse (other projects — e.g. a
# SigNoz dev clickhouse — commonly hold them)
for p in 8123 9000; do
  if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then
    echo "!! port $p is busy. Stop whatever holds it (docker ps; e.g. 'docker stop clickhouse zookeeper') and rerun." >&2
    exit 1
  fi
done

echo "== 1 · env"
if [[ ! -f librechat/.env ]]; then
  cp librechat/.env.example librechat/.env
  echo "   created librechat/.env — no OPENAI_API_KEY yet: narrator will use template narratives (still works)"
fi
# stale team key from a previous run must not leak into the new stack
sed -i '' '/^OTEL_EXPORTER_OTLP_HEADERS=/d' librechat/.env 2>/dev/null || true

echo "== 2 · observability half up (clickhouse + hyperdx + collector + seed)"
( cd librechat && docker compose up -d --wait clickhouse && \
  docker compose up -d hyperdx otel-collector hyperdx-seed )

echo "== 3 · data load (runs while you do the wizard)"
export CH_HOST=localhost CH_SECURE=0 CH_TRANSPORT=http \
       CH_USER=rca_rw CH_PASSWORD="${RCA_RW_PASSWORD:-rca_rw_dev}"
./load.sh --data-dir "$DATA_DIR"

# ORDER IS LOAD-BEARING: seen events must be enriched under the OLD dims before the
# unseen load truncates the dim tables and reloads the regenerated CSVs. Enrichment
# happens at insert time, so each slice keeps the attribute universe it was
# generated under.
if [[ -n "$UNSEEN_DIR" ]]; then
  echo "== 3b · unseen slice (dims from $UNSEEN_DIR replace the old ones)"
  ./load.sh --data-dir "$UNSEEN_DIR" --dataset unseen
fi

cat <<'EOF'

────────────────────────────────────────────────────────────
 YOUR TURN (the one manual moment):
 open http://localhost:8081 and complete the ClickHouse wizard:

   Connection Name  Stack ClickHouse
   Host             http://clickhouse:8123     (NOT localhost)
   Username         rca_rw
   Password         rca_rw_dev

 Test Connection → Create. Waiting here until it's done…
────────────────────────────────────────────────────────────
EOF
until [[ -n "$(cd librechat && docker compose exec -T mongodb mongosh --quiet \
    --eval 'var t=db.getSiblingDB("hyperdx").teams.findOne(); print(t?t._id:"")' 2>/dev/null)" ]]; do
  sleep 5
done
echo "== 5 · team detected — wiring trace export"
./librechat/wire_traces.sh

# the collector opens its OTLP receivers only after OpAMP delivers the team config —
# can lag the wizard by a minute+. Gate the pipeline so prefill spans aren't refused.
echo "== 5b · waiting for the collector's OTLP receiver"
for i in $(seq 1 36); do
  status=$(cd librechat && docker compose exec -T rca-mcp python -c "
import urllib.request, urllib.error
req = urllib.request.Request('http://otel-collector:4318/v1/traces', data=b'{}',
                             headers={'Content-Type': 'application/json'}, method='POST')
try:
    urllib.request.urlopen(req, timeout=3); print('up')
except urllib.error.HTTPError: print('up')
except Exception: print('down')" 2>/dev/null)
  [[ "$status" == "up" ]] && { echo "   receiver up"; break; }
  sleep 5
done

echo "== 6 · full stack"
( cd librechat && docker compose up -d )

cat <<'EOF'

════════════════════════════════════════════════════════════════════
Ingest done. Nothing has been investigated yet — that's your call:

   ./investigate.sh            profiler + sweep + prefill, one pass
                               per dataset (spans stream to HyperDX)

 Then:
 1. HyperDX   http://localhost:8081 — dashboard "RCA Overview" is
              seeded; set the time range to the loaded data
              (historical: the default range shows NOTHING).
 2. LibreChat http://localhost:3080 — register → create the RCA
              Analyst agent (librechat/README.md §5, ~2 min) → walk
              librechat/GOLDEN_QUESTIONS.md
════════════════════════════════════════════════════════════════════
EOF
