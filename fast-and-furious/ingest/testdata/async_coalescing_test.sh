#!/usr/bin/env bash
#
# Settles whether a per-request insert_deduplication_token defeats async-insert
# coalescing. It does not — see ingest/API_DESIGN.md §2 for the measured numbers.
#
# Needs a ClickHouse on localhost:18123 with password "test":
#   docker run -d --name async-test -p 18123:8123 \
#     -e CLICKHOUSE_PASSWORD=test clickhouse/clickhouse-server:latest

# Re-run with the arms SWAPPED (B first) to rule out a cold-start ordering effect,
# and confirm no rows were lost to false-positive dedup.
set -uo pipefail
CH='http://localhost:18123/?user=default&password=test'
N=60; ROWS=10; PAR=30
q() { curl -s "$CH" --data-binary "$1"; }

for t in t_tok t_notok; do
  q "DROP TABLE IF EXISTS $t" >/dev/null
  q "CREATE TABLE $t (id UInt64, s String, ts DateTime64(3,'UTC'))
     ENGINE = MergeTree ORDER BY id
     SETTINGS non_replicated_deduplication_window = 1000" >/dev/null
done
q "TRUNCATE TABLE system.asynchronous_insert_log" >/dev/null

rows() { local i=$1 j; for ((j=0;j<ROWS;j++)); do
  printf '{"id":%d,"s":"i-%d","ts":"2026-07-26 10:00:00.000"}\n' $((i*1000+j)) "$i"; done; }
export -f rows; export ROWS CH

# B FIRST this time
bs=$(date +%s.%N)
seq 0 $((N-1)) | xargs -P $PAR -I{} bash -c 'rows {} | curl -s -o /dev/null "$CH&async_insert=1&wait_for_async_insert=1&query=INSERT%20INTO%20t_notok%20FORMAT%20JSONEachRow" --data-binary @-'
be=$(date +%s.%N)

as=$(date +%s.%N)
seq 0 $((N-1)) | xargs -P $PAR -I{} bash -c 'rows {} | curl -s -o /dev/null "$CH&async_insert=1&wait_for_async_insert=1&insert_deduplication_token=tok-{}&query=INSERT%20INTO%20t_tok%20FORMAT%20JSONEachRow" --data-binary @-'
ae=$(date +%s.%N)

q "SYSTEM FLUSH LOGS" >/dev/null; sleep 3; q "SYSTEM FLUSH LOGS" >/dev/null

echo "=== rows landed (expect $((N*ROWS)) each — a shortfall would mean false-positive dedup) ==="
q "SELECT arm, rows FROM (
     SELECT 'A distinct token' AS arm, count() AS rows FROM t_tok
     UNION ALL SELECT 'B no token' AS arm, count() AS rows FROM t_notok
   ) ORDER BY arm FORMAT PrettyCompact"

echo
echo "=== COALESCING (B ran first this time) ==="
q "SELECT if(table='t_tok','A distinct token','B no token') AS arm,
          count() AS client_inserts, uniqExact(flush_query_id) AS server_flushes,
          round(count()/uniqExact(flush_query_id),2) AS inserts_per_flush,
          round(avg(bytes)) AS avg_bytes_per_insert
   FROM system.asynchronous_insert_log
   WHERE table IN ('t_tok','t_notok') AND status='Ok'
   GROUP BY table ORDER BY arm FORMAT PrettyCompact"

echo
printf "=== wall time: B(first)=%.2fs  A(second)=%.2fs ===\n" "$(echo "$be-$bs"|bc)" "$(echo "$ae-$as"|bc)"
