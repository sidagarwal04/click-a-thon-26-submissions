#!/usr/bin/env bash
# What every insight benchmark query READS, and proof it never touches raw_events.
#
#   ./scripts/bench_insights.sh                    # every file in sql/insights/benchmark/
#   ./scripts/bench_insights.sh session_facts_app_version_health
#
# Gate B of the plan is not "is it fast". It is: does the query read an approved serving table,
# is raw_events absent from the plan, are rows and bytes inside a documented budget, and does a
# filter prune where the physical design claims it does. So this captures read_rows, read_bytes,
# result_rows, memory, the table list and the EXPLAIN key condition for each shape, and it
# FAILS, rather than notes, if raw_events appears.
#
# Generic over the directory on purpose: the five remaining insight tables add a .sql file and
# get the whole artifact for free. Every benchmark query takes the same seven parameters as the
# serving queries, which is what makes that possible.
#
# CAPTURE METHOD, inherited from scripts/bench.sh where it was learned the hard way:
#   --query_id does NOT survive --queries-file on this client, so the SQL goes inline via
#   --query. SYSTEM FLUSH LOGS is retried INSIDE the loop, because one flush fired before the
#   log row exists is a flush that never helps. clusterAllReplicas, because the row may land on
#   another replica. NA is printed rather than a blank, so a missing number cannot be read as a
#   measured zero.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
export CH_DATABASE="$DB" EVIDENCE_STAMP_DB="$DB"
FROM="${FROM_TS:-2026-07-26 00:00:00}"
TO="${TO_TS:-2026-07-27 00:00:00}"
ONLY="${1:-}"

# shape | platform | country | video_type | app_version | content_id
SHAPES=(
  "unfiltered|||||0"
  "platform|ANDROID_PHONE||||0"
  "country||india|||0"
  "content|||||2078157818"
  "app_version||||6.34.8|0"
  "platform+country|ANDROID_PHONE|india|||0"
)

fail_any=0

measure() { # sql, plat, ctry, vtype, appv, cid, tag -> duration, rows, bytes, result_rows, mem, tables
  local sql="$1" plat="$2" ctry="$3" vtype="$4" appv="$5" cid="$6" tag="$7"
  local qid="ibench_${tag}_$$_${RANDOM}" row=""
  ./scripts/ch.sh --query "$sql" \
    --param_platform="$plat" --param_country="$ctry" --param_video_type="$vtype" \
    --param_app_version="$appv" --param_content_id="$cid" \
    --param_from_ts="$FROM" --param_to_ts="$TO" \
    --query_id="$qid" --format Null >/dev/null 2>&1 </dev/null || {
      # ERR in every cell, and the run is failed. Silently reporting NA here would let a query
      # that does not execute at all pass as a query with an unavailable measurement.
      echo "ERROR: benchmark query failed to execute for shape $tag" >&2
      fail_any=1; printf 'ERR\tERR\tERR\tERR\tERR\tERR'; return 0; }
  for _ in 1 2 3 4 5 6 7 8; do
    ./scripts/ch.sh --query "SYSTEM FLUSH LOGS" >/dev/null 2>&1 </dev/null || true
    row="$(./scripts/ch.sh --format TSVRaw --query "
      SELECT toString(query_duration_ms), toString(read_rows), toString(read_bytes),
             toString(result_rows), toString(memory_usage), arrayStringConcat(tables, ',')
      FROM clusterAllReplicas(default, system.query_log)
      WHERE type = 'QueryFinish' AND query_id = '$qid'" 2>/dev/null </dev/null | head -1)"
    [ -n "$row" ] && { printf '%s' "$row"; return 0; }
    sleep 2
  done
  echo "WARNING: no query_log row for $qid after 8 attempts" >&2
  printf 'NA\tNA\tNA\tNA\tNA\tNA'
}

bench_one() {
  local f="$1" name
  name="$(basename "$f" .sql)"
  local sql; sql="$(cat "$f")"
  local key plan
  local raw_hits=0

  {
    printf 'shape\tcold_ms\twarm_ms\tread_rows\tread_bytes\tresult_rows\tmemory_bytes\ttables_read\traw_scan\tkey_condition\n'
    for spec in "${SHAPES[@]}"; do
      IFS='|' read -r shape plat ctry vtype appv cid <<< "$spec"
      echo "  $name / $shape" >&2
      local cold warm tables raw key
      cold="$(measure "$sql" "$plat" "$ctry" "$vtype" "$appv" "$cid" cold)"
      warm="$(measure "$sql" "$plat" "$ctry" "$vtype" "$appv" "$cid" warm)"
      tables="$(echo "$warm" | cut -f6)"
      # The pass condition the plan states outright: raw_events absent from the plan. Checked
      # against the table list the SERVER recorded, not against the query text, because a view
      # can reach raw_events without naming it.
      case "$tables" in
        *raw_events*) raw="YES"; raw_hits=$((raw_hits + 1)) ;;
        *)            raw="no" ;;
      esac
      # Captured in two steps, not one pipeline. With `set -o pipefail` a failing EXPLAIN makes
      # the whole pipeline non-zero, `set -e` kills the script mid-loop, and the artifact is
      # written with a header and no rows: a benchmark that reports nothing and exits 0 through
      # the evidence pipe. That happened on the first run of this script, caused by an
      # ILLEGAL_AGGREGATION in the query it was measuring, and the harness hid the error rather
      # than reporting it. A measurement tool must never fail more quietly than what it measures.
      local plan=""
      plan="$(./scripts/ch.sh --format TSVRaw --query "EXPLAIN indexes = 1 $sql" \
                --param_platform="$plat" --param_country="$ctry" --param_video_type="$vtype" \
                --param_app_version="$appv" --param_content_id="$cid" \
                --param_from_ts="$FROM" --param_to_ts="$TO" 2>&1 </dev/null || true)"
      case "$plan" in
        *Exception*) key="EXPLAIN FAILED: $(printf '%s' "$plan" | grep -o 'Code: [0-9]*[^.]*\.' | head -1)"; fail_any=1 ;;
        *) key="$(printf '%s' "$plan" | tr -d '\r' | awk '
                /Condition:/ { sub(/^ *Condition: */, ""); cond = $0 }
                /Granules:/  { sub(/^ *Granules: */, "");  gran = $0 }
                END { if (cond == "") cond = "none (full scan)"; printf "%s ; granules %s", cond, (gran == "" ? "?" : gran) }')" ;;
      esac
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$shape" "$(echo "$cold" | cut -f1)" "$(echo "$warm" | cut -f1)" \
        "$(echo "$warm" | cut -f2)" "$(echo "$warm" | cut -f3)" "$(echo "$warm" | cut -f4)" \
        "$(echo "$warm" | cut -f5)" "$tables" "$raw" "$key"
    done
    printf '#\tquery\t%s\n'  "$f"
    printf '#\twindow\t%s -> %s\n' "$FROM" "$TO"
    printf '#\tservice\t%s\n' "$(./scripts/ch.sh --format TSVRaw --query "SELECT version()" 2>/dev/null | head -1)"
    printf '#\tuse_query_cache\t%s\n' "$(./scripts/ch.sh --format TSVRaw --query "SELECT value FROM system.settings WHERE name='use_query_cache'" 2>/dev/null | head -1)"
    printf 'gate.raw_events_in_plan\t%s\t(required 0)\t%s\n' "$raw_hits" "$([ "$raw_hits" = 0 ] && echo PASS || echo FAIL)"
  } | evidence "insight_bench_${name}" "read_rows, read_bytes, result_rows, tables and EXPLAIN key condition per filter shape for ${name}" \
    | xargs cat

  [ "$raw_hits" = 0 ] || fail_any=1
}

if [ -n "$ONLY" ]; then
  bench_one "sql/insights/benchmark/${ONLY}.sql"
else
  found=0
  for f in sql/insights/benchmark/*.sql; do
    [ -e "$f" ] || break
    found=1
    bench_one "$f"
  done
  [ "$found" = 1 ] || echo "no insight benchmark queries yet" >&2
fi

[ "$fail_any" = 0 ] || { echo "A BENCHMARK QUERY READ raw_events" >&2; exit 1; }
