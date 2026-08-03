#!/usr/bin/env bash
# check-mcp.sh — exercise the MCP server end to end, including what it must REFUSE.
#
#   ./ingest/cmd/sonyliv-mcp/check-mcp.sh                 against a local --transport http
#   MCP_URL=https://host:8848/mcp MCP_TOKEN=... ./check-mcp.sh
#
# An allowlist is only proven by what it turns away, so the negative cases below carry
# more weight than the positive ones and a missing refusal fails the run.
set -uo pipefail

url="${MCP_URL:-http://127.0.0.1:8848/mcp}"
token="${MCP_TOKEN:-}"
pass=0; fail=0

hdr=(-H 'Content-Type: application/json' -H 'Accept: application/json')
[[ -n "$token" ]] && hdr+=(-H "Authorization: Bearer $token")

rpc() { # rpc <method> <params-json>
  /usr/bin/curl -sS --max-time 90 "${hdr[@]}" -X POST "$url" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$1\",\"params\":$2}"
}

call() { # call <tool> <args-json>
  rpc tools/call "{\"name\":\"$1\",\"arguments\":$2}"
}

# expect <label> <substring> <payload>
expect() {
  if printf '%s' "$3" | grep -qF -- "$2"; then
    printf 'PASS  %s\n' "$1"; pass=$((pass+1))
  else
    printf 'FAIL  %s\n        wanted substring: %s\n        got: %.400s\n' "$1" "$2" "$3"
    fail=$((fail+1))
  fi
}

echo "== handshake =="
expect "initialize advertises tools/prompts/resources" '"protocolVersion"' \
  "$(rpc initialize '{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"1"}}')"
expect "initialize carries the additivity rule up front" 'NEVER SUM OR AVERAGE A PEAK' \
  "$(rpc initialize '{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"1"}}')"

tools="$(rpc tools/list '{}')"
for t in list_serving_tables data_freshness viewing_trend peak_and_average \
         rank_dimension top_titles detect_drops run_select_query; do
  expect "tools/list exposes $t" "\"$t\"" "$tools"
done

echo
echo "== knowledge =="
expect "guide resource is listed" 'sonyliv://serving/guide' "$(rpc resources/list '{}')"
expect "guide explains the grouping trap" '9,411.64' \
  "$(rpc resources/read '{"uri":"sonyliv://serving/guide"}')"
expect "investigate-drop prompt exists" 'investigate-drop' "$(rpc prompts/list '{}')"
expect "investigate-drop leads with freshness" 'data_freshness' \
  "$(rpc prompts/get '{"name":"investigate-drop"}')"

echo
echo "== reference figures (the numbers the whole project is graded on) =="
hot='{"from":"2026-07-26 10:00:00","to":"2026-07-26 11:00:00","grouping":"total"}'
r="$(call peak_and_average "$hot")"
expect "hot hour exact peak = 2305"          '2305'       "$r"
expect "hot hour average = 855.578199"       '855.578199' "$r"
expect "hot hour reads only 60 rows"         '60'         "$r"

echo
echo "== curated tools =="
expect "viewing_trend returns hourly buckets" '(2 rows)' \
  "$(call viewing_trend '{"from":"2026-07-26 10:00:00","to":"2026-07-26 12:00:00","grouping":"total","grain":"hour"}')"
expect "rank_dimension explains non-additive peaks" 'must not be added together' \
  "$(call rank_dimension '{"from":"2026-07-26 10:00:00","to":"2026-07-26 11:00:00","grouping":"platform"}')"
expect "top_titles resolves titles"          'viewer_hours' \
  "$(call top_titles '{"from":"2026-07-26 10:00:00","to":"2026-07-26 11:00:00","limit":5}')"
expect "data_freshness reports the minute layer" 'minute' "$(call data_freshness '{}')"
expect "list_serving_tables hides dim_mask"  'serving_minute_current' "$(call list_serving_tables '{}')"
expect "detect_drops finds the 07-26 ramp-down" 'retention' \
  "$(call detect_drops '{"from":"2026-07-26 11:00:00","to":"2026-07-26 11:40:00","grouping":"country"}')"

echo
echo "== refusals: per-user data =="
for tbl in events_clean events_dedup events_raw session_intervals fleet_sessions; do
  expect "run_select_query refuses $tbl" 'outside the serving layer' \
    "$(call run_select_query "{\"query\":\"SELECT count() FROM $tbl\"}")"
done
expect "refuses a database-qualified reach" 'outside the serving layer' \
  "$(call run_select_query '{"query":"SELECT count() FROM sonyliv_prod.events_clean"}')"
expect "refuses system tables" 'outside the serving layer' \
  "$(call run_select_query '{"query":"SELECT count() FROM system.query_log"}')"
expect "refuses a JOIN onto forbidden data" 'outside the serving layer' \
  "$(call run_select_query '{"query":"SELECT * FROM serving_watermark JOIN events_clean USING (x)"}')"
expect "refuses a payload hidden behind a comment" 'outside the serving layer' \
  "$(call run_select_query '{"query":"SELECT 1 /* harmless */ FROM /* still */ events_clean"}')"
expect "refuses a quoted identifier" 'outside the serving layer' \
  "$(call run_select_query "{\"query\":\"SELECT count() FROM \\\"events_clean\\\"\"}")"

echo
echo "== refusals: writes and escapes =="
expect "refuses INSERT"   'read-only' "$(call run_select_query '{"query":"INSERT INTO serving_watermark VALUES (1)"}')"
expect "refuses DROP"     'read-only' "$(call run_select_query '{"query":"DROP TABLE serving_watermark"}')"
expect "refuses GRANT"    'read-only' "$(call run_select_query '{"query":"GRANT SELECT ON *.* TO sonyliv_mcp"}')"
expect "refuses stacked statements" 'single statement' \
  "$(call run_select_query '{"query":"SELECT 1 FROM serving_watermark; DROP TABLE serving_watermark"}')"
expect "refuses url()"    'not permitted' "$(call run_select_query '{"query":"SELECT * FROM url('"'"'http://x'"'"')"}')"
expect "refuses remote()" 'not permitted' "$(call run_select_query '{"query":"SELECT * FROM remote('"'"'h'"'"',system,one)"}')"
expect "refuses clusterAllReplicas()" 'not permitted' \
  "$(call run_select_query '{"query":"SELECT * FROM clusterAllReplicas(default, system.one)"}')"

echo
echo "== allowed SQL still works =="
expect "a legitimate SELECT succeeds" 'rows)' \
  "$(call run_select_query '{"query":"SELECT grouping, count() FROM serving_minute_current GROUP BY grouping"}')"
expect "a CTE is not mistaken for a table" 'rows)' \
  "$(call run_select_query '{"query":"WITH t AS (SELECT 1 AS a FROM serving_watermark) SELECT * FROM t"}')"

echo
echo "== validation =="
expect "unknown grouping fails loudly" 'unknown grouping' \
  "$(call viewing_trend '{"from":"2026-07-26 10:00:00","to":"2026-07-26 11:00:00","grouping":"platfrom"}')"

if [[ -n "$token" ]]; then
  echo
  echo "== auth =="
  code="$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
     -H 'Content-Type: application/json' -X POST "$url" -d '{"jsonrpc":"2.0","id":1,"method":"ping"}')"
  expect "no token is rejected with 401" '401' "$code"
  code="$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
     -H 'Content-Type: application/json' -H 'Authorization: Bearer wrong' \
     -X POST "$url" -d '{"jsonrpc":"2.0","id":1,"method":"ping"}')"
  expect "a wrong token is rejected with 401" '401' "$code"
fi

echo
echo "$pass passed, $fail failed"
[[ $fail -eq 0 ]]
