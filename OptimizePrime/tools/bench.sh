#!/usr/bin/env bash
# tools/bench.sh — run our required-shape query matrix (evidence/benchmark/*.sql) against the
# graded Cloud database, READ-ONLY, and regenerate evidence/bench.txt.
#
# For every query: 1 EXPLAIN indexes=1 pass, then 3 timed runs with the query caches
# OFF (use_query_cache=0, use_query_condition_cache=0), median of the server-side
# elapsed_ns from X-ClickHouse-Summary (no SYSTEM FLUSH LOGS, no second query).
# Every run carries log_comment='bench:<query>:run<N>:<tag>' and its
# X-ClickHouse-Query-Id is recorded, so each number is findable in system.query_log.
#
# The Cloud service auto-suspends; the first query after idle has been measured at
# 29.3 s. warm_up() runs and DISCARDS a trivial query plus one real query before
# anything is timed.
#
# This script only ever sends SELECT / EXPLAIN. It never writes to the database.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

BENCH_DIR=evidence/benchmark
RESULTS="$BENCH_DIR/results"
BENCH_TAG="${BENCH_TAG:-bench-$(date -u +%Y%m%dT%H%M%SZ)}"
RUNS_PER_QUERY=3

H="${CH_HOST:?CH_HOST unset — fill in .env}"
H="${H#https://}"; H="${H#http://}"; H="${H%/}"
URL="https://${H}:${CH_PORT}/?database=${CH_DATABASE}"

mkdir -p "$RESULTS"
: > "$RESULTS/runs.tsv"

# ch_query <sql> <outfile> <format> [extra --url-query args...]
# Prints "<wall_seconds>\t<query_id>\t<summary_json>" on stdout.
ch_query() {
  local sql="$1" out="$2" fmt="$3"; shift 3
  local hdr wall qid summary
  hdr=$(mktemp)
  wall=$(curl -sS --fail-with-body -D "$hdr" -o "$out" -w '%{time_total}' \
    --user "${CH_USER}:${CH_PASSWORD}" \
    --url-query "wait_end_of_query=1" \
    --url-query "default_format=${fmt}" \
    "$@" "$URL" --data-binary "$sql")
  qid=$(grep -i '^x-clickhouse-query-id' "$hdr" | tail -1 | tr -d '\r' | cut -d' ' -f2)
  summary=$(grep -i '^x-clickhouse-summary' "$hdr" | tail -1 | tr -d '\r' | cut -d' ' -f2-)
  rm -f "$hdr"
  printf '%s\t%s\t%s\n' "$wall" "$qid" "$summary"
}

# Build --url-query param_* args from a .params sidecar (key=value per line).
param_args() {
  local pfile="$1"; PARAM_ARGS=()
  [ -f "$pfile" ] || return 0
  while IFS='=' read -r k v; do
    [ -n "$k" ] || continue
    PARAM_ARGS+=(--url-query "param_${k}=${v}")
  done < "$pfile"
}

echo "== warm-up (service auto-suspends; discard the first responses) =="
t0=$(mktemp)
ch_query "SELECT 1" "$t0" TSVRaw >/dev/null
param_args "$BENCH_DIR/b01_day_peak_avg_total.params"
ch_query "$(cat "$BENCH_DIR/b01_day_peak_avg_total.sql")" "$t0" TSVRaw "${PARAM_ARGS[@]}" >/dev/null
rm -f "$t0"
echo "   warm."

for qfile in "$BENCH_DIR"/b*.sql; do
  qid_name=$(basename "$qfile" .sql)
  sql=$(cat "$qfile")
  param_args "${qfile%.sql}.params"

  echo "== $qid_name =="

  # granule pruning, once per query
  ch_query "EXPLAIN indexes = 1 ${sql}" "$RESULTS/${qid_name}.explain.txt" TSVRaw \
    "${PARAM_ARGS[@]}" \
    --url-query "log_comment=bench-explain:${qid_name}:${BENCH_TAG}" >/dev/null

  # timed runs, caches off
  for run in $(seq 1 "$RUNS_PER_QUERY"); do
    body="$RESULTS/${qid_name}.run${run}.body"
    line=$(ch_query "$sql" "$body" PrettyCompactMonoBlock \
      "${PARAM_ARGS[@]}" \
      --url-query "use_query_cache=0" \
      --url-query "use_query_condition_cache=0" \
      --url-query "log_comment=bench:${qid_name}:run${run}:${BENCH_TAG}")
    sha=$(shasum -a 256 "$body" | cut -d' ' -f1)
    printf '%s\t%s\t%s\t%s\n' "$qid_name" "$run" "$sha" "$line" >> "$RESULTS/runs.tsv"
    echo "   run${run}: $(echo "$line" | cut -f2)"
  done

  # run 1 is the committed answer; all runs must agree (caches are off, data is static)
  mv "$RESULTS/${qid_name}.run1.body" "$RESULTS/${qid_name}.answer.txt"
  rm -f "$RESULTS/${qid_name}".run*.body
done

# metadata for the report
META="$RESULTS/meta.env"
{
  echo "BENCH_TAG=${BENCH_TAG}"
  echo "COMMIT=$(git rev-parse --short HEAD)"
  echo "TARGET=cloud database=${CH_DATABASE}"
} > "$META"
v=$(mktemp); ch_query "SELECT version()" "$v" TSVRaw >/dev/null
printf 'SERVER_VERSION=%s\n' "$(cat "$v")" >> "$META"; rm -f "$v"
c=$(mktemp)
ch_query "SELECT concat('ev_raw=', toString((SELECT count() FROM ev_raw)), ' session_intervals=', toString((SELECT count() FROM session_intervals)), ' cc_minute_delta=', toString((SELECT count() FROM cc_minute_delta)), ' cc_hour_agg=', toString((SELECT count() FROM cc_hour_agg)))" "$c" TSVRaw >/dev/null
printf 'ROW_COUNTS=%s\n' "$(cat "$c")" >> "$META"; rm -f "$c"
# dataset checksums: the sha256 pins in tools/fetch_data.sh are the source of truth
grep -Eo '"ch-hackathon-[a-z-]+\.csv +[0-9a-f]{64} +[0-9]+"' tools/fetch_data.sh \
  | tr -d '"' | awk '{printf "DATASET_SHA256_%d=%s %s (%s bytes)\n", NR, $1, $2, $3}' >> "$META"

python3 tools/bench_report.py
echo "== DONE — evidence/bench.txt regenerated (tag ${BENCH_TAG}) =="
