#!/usr/bin/env bash
# End-to-end smoke: sonyliv-api -> events_raw -> (MV) -> events_clean -> events_dedup
set -uo pipefail
cd /Users/sid/sonyliv-clickathon-2026/.claude/worktrees/api-design/ingest

export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=19000
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=smoke
export CLICKHOUSE_DATABASE=default
export CLICKHOUSE_SECURE=false
export SONYLIV_API_TOKEN=smoke-token

HTTP='http://localhost:18123/?user=default&password=smoke'
q() { curl -s "$HTTP" --data-binary "$1"; }

echo "=== apply schema (001-006) ==="
./bin/sonyliv-ingest schema 2>&1 | tail -4

echo
echo "=== start the API ==="
./bin/sonyliv-api --listen 127.0.0.1:18080 --sync-threshold 5 --batch-size 3 >/tmp/api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:18080/healthz >/dev/null 2>&1 && { echo "api up after ${i}s"; break; }
  sleep 1
done
echo "  healthz: $(curl -s http://127.0.0.1:18080/healthz)"
echo "  readyz:  $(curl -s http://127.0.0.1:18080/readyz)"

hex() { printf '%064X' "$1"; }
ev() { # $1 = n, $2 = event_type, $3 = event, $4 = ts offset ms
  printf '{"video_session_id":"%s","user_id":"%s","content_id":21311522,' "$(hex $1)" "$(hex $((1000+$1)))"
  printf '"event_type":"%s","event":"%s","event_timestamp":%d,' "$2" "$3" $((1785062007336+$4))
  printf '"session_start_epoch":1785062007336,"platform":"JIO_ANDROID_TV",'
  printf '"app_version":"3.9.4","country":"india","audio_language":"hin",'
  printf '"subtitle_language":"UNK","player_version":"1.8.2"}\n'
}

echo
echo "=== POST 1: unauthenticated (expect 401) ==="
curl -s -o /dev/null -w '  status=%{http_code}\n' -X POST http://127.0.0.1:18080/v1/events \
  -H 'Content-Type: application/x-ndjson' --data-binary "$(ev 1 VideoSessionStart VideoSessionStart 0)"

echo
echo "=== POST 2: 3 valid events, NDJSON, small -> async mode ==="
{ ev 1 VideoSessionStart VideoSessionStart 0; ev 1 VideoPlay Play 1692; ev 1 VideoHeartbeat network-activity 4000; } \
| curl -s -X POST http://127.0.0.1:18080/v1/events \
    -H "Authorization: Bearer $SONYLIV_API_TOKEN" -H 'Content-Type: application/x-ndjson' \
    --data-binary @- ; echo

echo
echo "=== POST 3: JSON array with one bad row (expect partial acceptance) ==="
printf '[%s,%s]' \
  "$(ev 2 VideoSessionStart VideoSessionStart 0 | tr -d '\n')" \
  '{"video_session_id":"too-short","user_id":"x","content_id":1,"event_timestamp":1785062007336,"session_start_epoch":1785062007336}' \
| curl -s -X POST http://127.0.0.1:18080/v1/events \
    -H "Authorization: Bearer $SONYLIV_API_TOKEN" -H 'Content-Type: application/json' \
    --data-binary @- ; echo

echo
echo "=== POST 4: 6 events -> over --sync-threshold 5, expect sync + 2 batches at --batch-size 3 ==="
{ for i in 3 4 5 6 7 8; do ev $i VideoHeartbeat buffer-health $((i*1000)); done; } \
| curl -s -X POST http://127.0.0.1:18080/v1/events \
    -H "Authorization: Bearer $SONYLIV_API_TOKEN" -H 'Content-Type: application/x-ndjson' \
    --data-binary @- ; echo

echo
echo "=== POST 5: replay POST 2 byte-for-byte (idempotency: rows must NOT double) ==="
{ ev 1 VideoSessionStart VideoSessionStart 0; ev 1 VideoPlay Play 1692; ev 1 VideoHeartbeat network-activity 4000; } \
| curl -s -X POST http://127.0.0.1:18080/v1/events \
    -H "Authorization: Bearer $SONYLIV_API_TOKEN" -H 'Content-Type: application/x-ndjson' \
    --data-binary @- ; echo

sleep 3
q "SYSTEM FLUSH LOGS" >/dev/null

echo
echo "=== rows landed ==="
q "SELECT 'events_raw' AS t, count() AS rows FROM events_raw
   UNION ALL SELECT 'events_clean', count() FROM events_clean
   UNION ALL SELECT 'events_dedup', count() FROM events_dedup
   ORDER BY t FORMAT PrettyCompact"

echo
echo "=== the MV classified signals correctly ==="
q "SELECT signal, count() AS n FROM events_clean GROUP BY signal ORDER BY signal FORMAT PrettyCompact"

echo
echo "=== ids upper-cased, content_id signed, session_key materialized ==="
q "SELECT DISTINCT substring(video_session_id,1,8) AS vsid_prefix, content_id, session_key != 0 AS key_set
   FROM events_clean ORDER BY vsid_prefix LIMIT 4 FORMAT PrettyCompact"

echo
echo "=== quarantined rows ==="
q "SELECT source, reason, source_line, detail FROM ingest_rejects ORDER BY source_line FORMAT PrettyCompact"

echo
echo "=== batch audit (one row per acknowledged chunk) ==="
q "SELECT source, batch_ordinal, row_count, status FROM ingest_batches ORDER BY started_at, batch_ordinal FORMAT PrettyCompact"

echo
echo "=== /v1/stats ==="
curl -s -H "Authorization: Bearer $SONYLIV_API_TOKEN" http://127.0.0.1:18080/v1/stats; echo

echo
echo "=== graceful shutdown on SIGTERM ==="
kill -TERM $API_PID; sleep 2
tail -3 /tmp/api.log
