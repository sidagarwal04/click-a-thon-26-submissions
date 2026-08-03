#!/usr/bin/env bash
# tools/clickstack-sources.sh — point the local ClickStack at OUR concurrency data.
#
# clickstack-bootstrap.sh gets you a team and an OTLP key; that covers ClickStack
# observing our pipeline. This script covers the other direction: making HyperDX
# chart the concurrency the problem statement asks us to visualise.
#
# It registers a ClickHouse *connection* to the graded Cloud service and
# *sources* over the concurrency views. Idempotent — re-running updates each
# named source to the committed definition and creates no duplicates.
#
# Why Cloud and not the local container: Cloud is the graded target and holds the
# schema that matches sql/. ClickStack itself still runs locally; only the data
# it reads is remote.
#
#   tools/clickstack-sources.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

: "${CS_EMAIL:?set CS_EMAIL in .env}"
: "${CS_PASSWORD:?set CS_PASSWORD in .env}"
: "${CH_HOST:?set CH_HOST in .env}"
: "${CH_PASSWORD:?set CH_PASSWORD in .env}"

BASE=http://localhost:8000
JAR=$(mktemp -t cs-cookies.XXXXXX)
trap 'rm -f "$JAR"' EXIT

ch_host() { local h="$CH_HOST"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }
CONN_NAME="SonyLIV Cloud"

curl -sf -o /dev/null "$BASE/health" || { echo "ClickStack is not up — run: make stack-up" >&2; exit 1; }

curl -sS -c "$JAR" -X POST "$BASE/login/password" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CS_EMAIL\",\"password\":\"$CS_PASSWORD\"}" -o /dev/null \
  || { echo "login failed — run tools/clickstack-bootstrap.sh first" >&2; exit 1; }

# --- connection -------------------------------------------------------------
CONN_ID=$(curl -sS -b "$JAR" "$BASE/connections" | CONN_NAME="$CONN_NAME" python3 -c '
import json, os, sys
name = os.environ["CONN_NAME"]
for c in json.load(sys.stdin):
    if c.get("name") == name:
        print(c.get("id") or c.get("_id", "")); break
')

if [ -n "$CONN_ID" ]; then
  echo "connection '$CONN_NAME' exists ($CONN_ID)"
else
  CONN_ID=$(curl -sS -b "$JAR" -X POST "$BASE/connections" -H 'Content-Type: application/json' \
    -d "{\"name\":\"$CONN_NAME\",\"host\":\"https://$(ch_host):${CH_PORT:-8443}\",\"username\":\"${CH_USER:-default}\",\"password\":\"${CH_PASSWORD}\"}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or d.get("_id",""))')
  [ -n "$CONN_ID" ] || { echo "failed to create connection" >&2; exit 1; }
  echo "created connection '$CONN_NAME' ($CONN_ID)"
fi

# --- sources ----------------------------------------------------------------
# kind=log is the generic table source in HyperDX; timestampValueExpression is
# what makes `minute` the time axis every chart draws against. PUT is a full
# replace and requires id in the body; a successful self-hosted PUT returns an
# empty 200 response, so HTTP status—not a JSON body—is the success contract.
add_source() {  # add_source <display name> <table> <select expression>
  local name="$1" table="$2" select="$3" existing payload response
  existing=$(curl -sS -b "$JAR" "$BASE/sources" | SRC_NAME="$name" python3 -c '
import json, os, sys
name = os.environ["SRC_NAME"]
print(next((s.get("id") or s.get("_id","") for s in json.load(sys.stdin) if s.get("name") == name), ""))
')
  payload=$(SOURCE_NAME="$name" SOURCE_TABLE="$table" SOURCE_SELECT="$select" \
    SOURCE_DB="${CH_DATABASE:-sonyliv}" SOURCE_CONNECTION="$CONN_ID" \
    SOURCE_ID="$existing" python3 -c '
import json, os
payload = {
    "name": os.environ["SOURCE_NAME"],
    "kind": "log",
    "connection": os.environ["SOURCE_CONNECTION"],
    "from": {
        "databaseName": os.environ["SOURCE_DB"],
        "tableName": os.environ["SOURCE_TABLE"],
    },
    "timestampValueExpression": "minute",
    "defaultTableSelectExpression": os.environ["SOURCE_SELECT"],
}
if os.environ["SOURCE_ID"]:
    payload["id"] = os.environ["SOURCE_ID"]
print(json.dumps(payload))
')
  if [ -n "$existing" ]; then
    response=$(printf '%s' "$payload" | curl -fsS -b "$JAR" -X PUT \
      "$BASE/sources/$existing" -H 'Content-Type: application/json' --data-binary @-) \
      || { echo "failed to update source '$name' ($existing)" >&2; exit 1; }
    echo "updated source '$name' ($existing)"
  else
    response=$(printf '%s' "$payload" | curl -fsS -b "$JAR" -X POST \
      "$BASE/sources" -H 'Content-Type: application/json' --data-binary @-) \
      || { echo "failed to create source '$name'" >&2; exit 1; }
    SOURCE_NAME="$name" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
source_id = d.get("id") or d.get("_id", "")
if not source_id:
    raise SystemExit("source create response has no id")
print("created source %r (%s)" % (os.environ["SOURCE_NAME"], source_id))
' <<<"$response"
  fi
}

add_source "Concurrency (minute)"       v_concurrency_minute_stateless "minute, platform, country, content_id, concurrent"
add_source "Concurrency total (minute)" v_concurrency_minute_total     "minute, concurrent"
add_source "Session minutes (filters)"  v_session_minutes              "minute, video_session_id, user_id, platform, country, content_id, title, video_type, category, show_name, content_dimensions, app_version, audio_language, subtitle_language, player_version, video_resolution, extra_dimensions"
add_source "Dynamic event dimensions"   v_dynamic_dimension_values     "minute, video_session_id, user_id, dimension_name, dimension_value"
add_source "Dynamic content dimensions" v_dynamic_content_dimension_values "minute, video_session_id, user_id, content_id, dimension_name, dimension_value"

echo
echo "HyperDX UI: http://localhost:8080"
echo "  Search -> source 'Concurrency total (minute)' -> chart concurrent over minute"
# The single most common way to conclude "the charts are broken": HyperDX opens
# on a "last 15 minutes" window and the dataset ends 2026-07-26.
echo "  Set the time range to 2026-07-14 → 2026-07-26. The dataset is NOT 'now',"
echo "  and the default 'last 15 minutes' window renders an empty chart."
