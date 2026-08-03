#!/bin/bash
# One-time provisioning: creates the ClickHouse Cloud connection, source, saved
# search, webhook, and alert inside a FRESH HyperDX instance, so the demo
# doesn't depend on manually clicking through the UI. ClickHouse itself needs
# no setup -- inmobi_unseen (including alerts_live_confirmed) already exists
# on the shared ClickHouse Cloud instance; this script only creates objects
# inside HyperDX's own local Mongo.
#
# Prereqs:
#   1. ClickStack (HyperDX) is up: docker compose up -d  (in the ClickStack dir)
#   2. You've signed up once at http://localhost:8080 and grabbed your personal
#      access key from Team Settings -> API Keys (NOT the team ingestion key).
#
# Usage:
#   HYPERDX_ACCESS_KEY=... CH_PASSWORD=... ./setup_hyperdx.sh
#
# Prints the new alert's webhook target (point your llm_rca_agent.py there)
# and confirms everything was created. Safe to re-run -- it always creates
# fresh objects rather than upserting, so if you re-run it, delete the old
# ones first (see cleanup notes at the bottom).

set -e

: "${HYPERDX_ACCESS_KEY:?Set HYPERDX_ACCESS_KEY to your personal API key from HyperDX -> Team Settings -> API Keys}"
: "${CH_PASSWORD:?Set CH_PASSWORD to the shared ClickHouse Cloud password}"
CH_HOST="${CH_HOST:-fc5trrzotn.ap-south-1.aws.clickhouse.cloud}"
HYPERDX_URL="${HYPERDX_URL:-http://localhost:8000}"
AGENT_WEBHOOK_URL="${AGENT_WEBHOOK_URL:-http://host.docker.internal:9203/hyperdx-hook}"
AUTH=(-H "Authorization: Bearer $HYPERDX_ACCESS_KEY")

echo "== 1/5: ClickHouse Cloud connection =="
CONN_ID=$(curl -s -X POST "$HYPERDX_URL/api/v2/connections" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"name\": \"ClickHouse Cloud (inmobi_unseen)\",
  \"host\": \"https://$CH_HOST:8443\",
  \"username\": \"default\",
  \"password\": \"$CH_PASSWORD\"
}" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")
echo "connection: $CONN_ID"

echo "== 2/5: source (alerts_live_confirmed -- pre-filtered to real, persistent incidents) =="
SOURCE_ID=$(curl -s -X POST "$HYPERDX_URL/api/v2/sources" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"name\": \"InMobi Unseen Alerts Live (confirmed)\",
  \"kind\": \"log\",
  \"connection\": \"$CONN_ID\",
  \"from\": {\"databaseName\": \"inmobi_unseen\", \"tableName\": \"alerts_live_confirmed\"},
  \"timestampValueExpression\": \"window_hour\",
  \"defaultTableSelectExpression\": \"window_hour,metric,observed,baseline,robust_z,severity,sample_requests\",
  \"serviceNameExpression\": \"metric\",
  \"bodyExpression\": \"metric\",
  \"displayedTimestampValueExpression\": \"window_hour\",
  \"implicitColumnExpression\": \"metric\"
}" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")
echo "source: $SOURCE_ID"

echo "== 3/5: saved search (no WHERE clause -- the confirmed-only filtering already lives in the view) =="
SEARCH_ID=$(curl -s -X POST "$HYPERDX_URL/api/v2/saved-searches" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"name\": \"InMobi Unseen confirmed incidents (LLM agent)\",
  \"select\": \"window_hour,metric,observed,baseline,robust_z,severity,sample_requests\",
  \"where\": \"\",
  \"whereLanguage\": \"sql\",
  \"orderBy\": \"window_hour ASC\",
  \"sourceId\": \"$SOURCE_ID\",
  \"tags\": []
}" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")
echo "saved search: $SEARCH_ID"

echo "== 4/5: webhook -> the LLM agent's Flask endpoint =="
WEBHOOK_ID=$(curl -s -X POST "$HYPERDX_URL/api/v2/webhooks" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"name\": \"InMobi Unseen LLM RCA agent\",
  \"url\": \"$AGENT_WEBHOOK_URL\",
  \"description\": \"agent/llm_rca_agent.py -- Claude Haiku 4.5 with live SQL tool access against inmobi_unseen.\",
  \"service\": \"generic\",
  \"body\": \"{\\\"startTime\\\": {{startTime}}, \\\"endTime\\\": {{endTime}} }\"
}" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")
echo "webhook: $WEBHOOK_ID"

echo "== 5/5: alert (threshold=1 so OK really means OK, not 'count>=0') =="
ALERT_ID=$(curl -s -X POST "$HYPERDX_URL/api/v2/alerts" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"name\": \"InMobi Unseen LLM RCA agent triggered\",
  \"message\": \"InMobi unseen-dataset breach in alerts_live -- handing off to the real LLM agent (Claude Haiku 4.5 with live SQL tool access).\",
  \"threshold\": 1,
  \"interval\": \"1h\",
  \"thresholdType\": \"above\",
  \"source\": \"saved_search\",
  \"channel\": {\"type\": \"webhook\", \"webhookId\": \"$WEBHOOK_ID\"},
  \"savedSearchId\": \"$SEARCH_ID\"
}" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")
echo "alert: $ALERT_ID"

echo
echo "Done. Saved search '$SEARCH_ID' should show 155 rows once you set its date range to Jul 6-11, 2026."
echo "trigger_demo_alert.sh looks the alert up by name, so no further config needed."
echo
echo "To tear down and re-run this script cleanly:"
echo "  curl -X DELETE $HYPERDX_URL/api/v2/alerts/$ALERT_ID -H \"Authorization: Bearer \$HYPERDX_ACCESS_KEY\""
echo "  curl -X DELETE $HYPERDX_URL/api/v2/webhooks/$WEBHOOK_ID -H \"Authorization: Bearer \$HYPERDX_ACCESS_KEY\""
echo "  curl -X DELETE $HYPERDX_URL/api/v2/saved-searches/$SEARCH_ID -H \"Authorization: Bearer \$HYPERDX_ACCESS_KEY\""
