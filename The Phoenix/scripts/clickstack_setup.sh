#!/usr/bin/env bash
# Provisions the ClickStack/HyperDX side of the integration, idempotently.
#
#   cd docker/clickstack && docker compose --env-file ../../.env up -d
#   ./scripts/clickstack_setup.sh
#   open http://localhost:8090
#
# WHY A SCRIPT AND NOT A LIST OF CLICKS. TASK.md 2.1 asks for panel definitions documented so
# the dashboard is reproducible on a fresh laptop. A screenshot is not reproducible and a list
# of UI steps rots. This runs against HyperDX's own REST API, so the dashboard is rebuilt from
# source, and the panel SQL below is the actual definition rather than a description of one.
#
# THE TRAP THIS SCRIPT EXISTS TO CLOSE, measured rather than assumed. The all-in-one image takes
# CLICKHOUSE_ENDPOINT and points its OTel COLLECTOR at our Cloud service, which is real: the
# otel_* tables are created in our service, not in the container. But the HyperDX APP still
# ships with a connection called "Local ClickHouse" pointing at http://localhost:8123, the
# BUNDLED instance. So a green container, populated otel tables, and a working UI are all true
# at once while every chart still reads the wrong database. Verified by listing
# /api/connections after a clean `up -d`: host was http://localhost:8123.
#
# This script therefore creates a SECOND connection to our Cloud service and hangs the phoenix
# source and every panel off that one.
set -euo pipefail
cd "$(dirname "$0")/.."

HDX="${HDX_URL:-http://localhost:8090}"
EMAIL="${HDX_EMAIL:-phoenix@example.com}"
PASSWORD="${HDX_PASSWORD:-PhoenixClickathon2026!}"
JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT

set -a; [ -f .env ] && . ./.env; set +a
: "${CH_HOST:?no CH_HOST: cp .env.example .env and fill it in}"

api() { curl -sS -b "$JAR" --max-time 60 -H 'content-type: application/json' "$@"; }
# HyperDX speaks HTTPS on 8443, never the native 9440 in .env. Same distinction the frontend
# got wrong.
CH_ENDPOINT="https://${CH_HOST}:8443"

echo "== 1. account" >&2
if [ "$(curl -sS --max-time 30 "$HDX/api/installation" | grep -c 'true')" = 0 ]; then
  curl -sS --max-time 60 -o /dev/null -H 'content-type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"confirmPassword\":\"$PASSWORD\"}" \
    "$HDX/api/register/password"
  echo "   created team for $EMAIL" >&2
else
  echo "   team already exists" >&2
fi
curl -sS -c "$JAR" --max-time 60 -o /dev/null -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" "$HDX/api/login/password"
api "$HDX/api/me" | grep -q '"email"' || { echo "LOGIN FAILED" >&2; exit 1; }

echo "== 2. connection to our Cloud service (not the bundled ClickHouse)" >&2
CONN="$(api "$HDX/api/connections" | python3 -c "
import json,sys
for c in json.load(sys.stdin):
    if c.get('name') == 'Phoenix ClickHouse Cloud': print(c['id']); break
")"
if [ -z "$CONN" ]; then
  CONN="$(api -X POST -d "{\"name\":\"Phoenix ClickHouse Cloud\",\"host\":\"$CH_ENDPOINT\",\"username\":\"${CH_USER:-default}\",\"password\":\"${CH_PASSWORD}\"}" \
    "$HDX/api/connections" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id') or d['_id'])")"
fi
echo "   connection $CONN -> $CH_ENDPOINT" >&2

echo "== 3. source: phoenix.concurrency_deltas" >&2
SRC="$(api "$HDX/api/sources" | python3 -c "
import json,sys
for s in json.load(sys.stdin):
    if s.get('name') == 'Phoenix concurrency deltas': print(s['id']); break
")"
if [ -z "$SRC" ]; then
  SRC="$(api -X POST -d "{
    \"name\": \"Phoenix concurrency deltas\",
    \"kind\": \"log\",
    \"connection\": \"$CONN\",
    \"from\": {\"databaseName\": \"phoenix\", \"tableName\": \"concurrency_deltas\"},
    \"timestampValueExpression\": \"minute\",
    \"implicitColumnExpression\": \"platform\",
    \"defaultTableSelectExpression\": \"minute, platform, country, video_type, app_version, content_id, delta\"
  }" "$HDX/api/sources" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id') or d['_id'])")"
fi
echo "   source $SRC" >&2

# ---------------------------------------------------------------------------------------------
# PANEL DEFINITIONS. These are the definitions, not a description of them.
#
# Every panel obeys the two rules the delta model imposes, and TASK.md 2.1 names both:
#
#   sum(delta) WITH A RUNNING TOTAL. A row in concurrency_deltas is a CHANGE, not a level. A
#   panel that plots delta directly plots the first derivative and reads as noise around zero.
#   The cumulative sum must also start at the first minute of the series, never at the panel's
#   own time bound, or the curve starts at zero and undercounts every session already watching.
#
#   NO FINAL. concurrency_deltas is a SummingMergeTree, so sum(delta) is correct whether or not
#   a merge has happened. FINAL would force merge-on-read across the whole part set, which is
#   the cost this schema exists to avoid.
#
# These panels are deliberately LIVE: no frozen_before predicate. That is the split between the
# two surfaces, and it is intentional rather than an oversight. ClickStack is the operational
# view and answers "is the pipeline healthy right now"; the Next.js console is the validated
# view and answers "what is the graded number", frozen to the corpus every artifact in evidence/
# was measured against. A panel here showing 88.20 would be a panel that cannot show ingest lag.
# ---------------------------------------------------------------------------------------------

read -r -d '' CURVE_SQL <<'SQL' || true
SELECT minute,
       toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent_sessions
FROM (SELECT minute, sum(delta) AS d FROM phoenix.concurrency_deltas GROUP BY minute)
ORDER BY minute ASC
SQL

read -r -d '' PLATFORM_SQL <<'SQL' || true
SELECT platform,
       max(c) AS peak_concurrent_sessions
FROM (
    SELECT platform, minute,
           toInt64(sum(d) OVER (PARTITION BY platform ORDER BY minute ASC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
    FROM (SELECT platform, minute, sum(delta) AS d
          FROM phoenix.concurrency_deltas GROUP BY platform, minute)
)
GROUP BY platform
ORDER BY peak_concurrent_sessions DESC
SQL

read -r -d '' COUNTRY_SQL <<'SQL' || true
SELECT country,
       max(c) AS peak_concurrent_sessions
FROM (
    SELECT country, minute,
           toInt64(sum(d) OVER (PARTITION BY country ORDER BY minute ASC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
    FROM (SELECT country, minute, sum(delta) AS d
          FROM phoenix.concurrency_deltas GROUP BY country, minute)
)
GROUP BY country
ORDER BY peak_concurrent_sessions DESC
SQL

# Watermark lag: how far the newest event we hold is behind wall clock. This is the ingest-lag
# number TASK.md 2.1 calls out as a judging criterion. Reads raw_events, deliberately, because
# the question is about ARRIVAL and the delta table is one derivation step behind it.
#
# NOT ingested_at. That column was added by a later ALTER, ClickHouse does not rewrite existing
# parts, so for the pre-ALTER rows its DEFAULT now() is evaluated at READ time and equals the
# reading query's own wall clock. Proven in evidence/ingested_at_nondeterminism. A lag panel
# built on it would read a confident, meaningless zero.
read -r -d '' LAG_SQL <<'SQL' || true
SELECT dateDiff('second', max(event_timestamp), now()) AS event_watermark_lag_seconds,
       max(event_timestamp)                            AS newest_event,
       count()                                         AS rows_held
FROM phoenix.raw_events
SQL

# Layer 3: what the serving queries actually read, straight from system.query_log on the same
# service. read_rows and read_bytes against the committed budgets are a named judging criterion,
# which is the whole argument for putting them in the observability tool rather than beside it.
read -r -d '' READS_SQL <<'SQL' || true
SELECT query_id,
       toStartOfMinute(event_time) AS minute,
       read_rows,
       read_bytes,
       toUInt64(query_duration_ms) AS elapsed_ms,
       tables
FROM clusterAllReplicas(default, system.query_log)
WHERE type = 'QueryFinish'
  AND event_time > now() - INTERVAL 6 HOUR
  AND hasAny(tables, ['phoenix.concurrency_deltas', 'phoenix.user_concurrency_deltas',
                      'phoenix.session_minute_runs', 'phoenix.user_minute_runs'])
ORDER BY event_time DESC
LIMIT 200
SQL

echo "== 4. dashboard" >&2
tile() { python3 -c "
import json,sys
print(json.dumps({'id':sys.argv[1],'x':int(sys.argv[2]),'y':int(sys.argv[3]),
                  'w':int(sys.argv[4]),'h':int(sys.argv[5]),
                  'config':{'configType':'sql','sqlTemplate':sys.argv[6],
                            'connection':sys.argv[7],'name':sys.argv[8]}}))
" "$@"; }

TILES="$(python3 -c "
import sys
print('[' + ','.join(sys.argv[1:]) + ']')
" \
  "$(tile curve     0 0 12 4 "$CURVE_SQL"    "$CONN" 'Concurrent sessions per minute, running total of sum(delta)')" \
  "$(tile lag       0 4  4 3 "$LAG_SQL"      "$CONN" 'Event watermark lag, seconds behind wall clock')" \
  "$(tile platform  4 4  4 3 "$PLATFORM_SQL" "$CONN" 'Peak concurrent sessions by platform')" \
  "$(tile country   8 4  4 3 "$COUNTRY_SQL"  "$CONN" 'Peak concurrent sessions by country')" \
  "$(tile reads     0 7 12 4 "$READS_SQL"    "$CONN" 'Serving query reads: read_rows, read_bytes, elapsed_ms by query_id')")"

DASH="$(api "$HDX/api/dashboards" | python3 -c "
import json,sys
for d in json.load(sys.stdin):
    if d.get('name') == 'Phoenix Foreground Concurrency': print(d['id']); break
")"
BODY="$(python3 -c "
import json,sys
print(json.dumps({'name':'Phoenix Foreground Concurrency','tags':['phoenix'],
                  'tiles':json.loads(sys.stdin.read())}))
" <<<"$TILES")"

if [ -z "$DASH" ]; then
  DASH="$(api -X POST -d "$BODY" "$HDX/api/dashboards" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id') or d['_id'])")"
  echo "   created dashboard $DASH" >&2
else
  api -X PATCH -d "$BODY" "$HDX/api/dashboards/$DASH" > /dev/null
  echo "   updated dashboard $DASH" >&2
fi

echo "== 5. verify HyperDX itself reads OUR service, not its bundled one" >&2
# This is the step that makes the whole thing checkable rather than claimed. Running the panel
# SQL against ClickHouse directly proves the SQL is valid; it proves nothing about which database
# HyperDX will use. So run it through HyperDX's own proxy, pinned to the connection the panels
# use, and require rows back. If the app ever falls back to the bundled ClickHouse, phoenix.*
# does not exist there and this fails loudly.
proxy() {
  curl -sSL -b "$JAR" -H "x-hyperdx-connection-id: $CONN" -H 'content-type: text/plain' \
    --max-time 60 -X POST --data-binary "$1" "$HDX/api/clickhouse-proxy"
}
verify="$(proxy "SELECT count() FROM phoenix.concurrency_deltas FORMAT TSV" | tr -d '[:space:]')"
case "$verify" in
  ''|*[!0-9]*) echo "FAIL: HyperDX could not read phoenix.concurrency_deltas: $verify" >&2; exit 1;;
esac
[ "$verify" -gt 0 ] || { echo "FAIL: phoenix.concurrency_deltas read 0 rows through HyperDX" >&2; exit 1; }
echo "   HyperDX read $verify delta rows from phoenix via connection $CONN" >&2

lag="$(proxy "SELECT dateDiff('second', max(event_timestamp), now()) FROM phoenix.raw_events FORMAT TSV" | tr -d '[:space:]')"
echo "   watermark lag through HyperDX: ${lag}s" >&2

echo >&2
echo "ClickStack ready: $HDX/dashboards/$DASH" >&2
echo "  login: $EMAIL / $PASSWORD" >&2
