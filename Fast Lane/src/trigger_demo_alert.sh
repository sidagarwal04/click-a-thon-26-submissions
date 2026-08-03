#!/bin/bash
# Demo trigger: flips the HyperDX alert's UI state from OK -> ALERT using the
# REAL alerts_live numbers for the chosen incident (no fabricated data --
# HyperDX's own cron only evaluates real wall-clock time, and the dataset is
# historical, so this step stands in for that state flip), then immediately
# POSTs the exact webhook payload HyperDX would send at the LLM agent's
# endpoint, for one of the two verified, segment-attributed incidents.
#
# Requires HYPERDX_ACCESS_KEY (Team Settings -> API Keys in HyperDX) so the
# alert can be looked up by name -- portable across machines, no hardcoded ID.
#
# Usage: HYPERDX_ACCESS_KEY=... ./trigger_demo_alert.sh [video|ios]
#   video (default) -- ecpm P1, Jul 9 08:00-09:00, ad_format=video rate fault
#   ios             -- fill_rate P2, Jul 8 03:00-04:00, os_version=iOS 17.5 rate fault
#
# Run ./trigger_demo_alert.sh reset beforehand to confirm the alert is at OK.

set -e

: "${HYPERDX_ACCESS_KEY:?Set HYPERDX_ACCESS_KEY to your personal API key from HyperDX -> Team Settings -> API Keys}"
HYPERDX_URL="${HYPERDX_URL:-http://localhost:8000}"
AGENT_URL="${AGENT_URL:-http://localhost:9203}"
ALERT_NAME="${ALERT_NAME:-InMobi Unseen LLM RCA agent triggered}"
MONGO_CONTAINER="${MONGO_CONTAINER:-clickstack-db-1}"

CASE="${1:-video}"

ALERT_ID=$(curl -s "$HYPERDX_URL/api/v2/alerts" -H "Authorization: Bearer $HYPERDX_ACCESS_KEY" \
  | python3 -c "
import json, sys
for a in json.load(sys.stdin)['data']:
    if a['name'] == '$ALERT_NAME':
        print(a['id']); break
")
if [ -z "$ALERT_ID" ]; then
  echo "No alert named '$ALERT_NAME' found -- run setup_hyperdx.sh first." >&2
  exit 1
fi

set_state() {
  docker exec "$MONGO_CONTAINER" mongosh --quiet --eval "db.getSiblingDB('hyperdx').alerts.updateOne({_id: ObjectId('$ALERT_ID')}, {\$set: {state: '$1'}})" > /dev/null
}

if [ "$CASE" = "reset" ]; then
  set_state "OK"
  echo "Alert reset to OK."
  exit 0
fi

if [ "$CASE" = "video" ]; then
  START_ISO="2026-07-09T08:00:00"
  echo "Incident: ecpm P1, Jul 9 08:00-09:00 -- observed 2.1549 vs baseline 2.4787 (-13.06%, z=-16.32)"
  echo "Expect: ad_format=video, rate fault, ~29.6% eCPM collapse in that segment"
elif [ "$CASE" = "ios" ]; then
  START_ISO="2026-07-08T03:00:00"
  echo "Incident: fill_rate P2, Jul 8 03:00-04:00 -- observed 0.7317 vs baseline 0.7873 (-7.05%, z=-8.52)"
  echo "Expect: os_version=iOS 17.5, rate fault"
else
  echo "Unknown case '$CASE' -- use 'video', 'ios', or 'reset'" >&2
  exit 1
fi

echo
echo "-- flipping alert state OK -> ALERT (HyperDX Alerts page) --"
set_state "ALERT"
sleep 1

START_MS=$(python3 -c "import datetime; print(int(datetime.datetime.fromisoformat('$START_ISO').replace(tzinfo=datetime.timezone.utc).timestamp()*1000))")
END_MS=$(python3 -c "print($START_MS + 3600000)")

echo "-- firing the real webhook: POST $AGENT_URL/hyperdx-hook {startTime: $START_MS, endTime: $END_MS} --"
echo

curl -s -X POST "$AGENT_URL/hyperdx-hook" \
  -H "Content-Type: application/json" \
  -d "{\"startTime\": $START_MS, \"endTime\": $END_MS}" | python3 -m json.tool

echo
echo "Check Langfuse for the new AgentExecutor trace, and rca_results for the new row."
echo "Run './trigger_demo_alert.sh reset' to put the alert back to OK before the next run."
