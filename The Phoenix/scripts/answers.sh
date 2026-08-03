#!/usr/bin/env bash
# THE CONCURRENCY RESULTS ARTIFACT. Deliverables 1 and 2 of the unseen day, in one stamped file.
#
#   ./scripts/answers.sh                  # against $CH_DATABASE, then phoenix_unseen
#   ./scripts/answers.sh phoenix_unseen
#   FROM=... TO=... ./scripts/answers.sh phoenix_unseen
#
# WHY THIS EXISTS SEPARATELY FROM bench.sh. bench.sh measures what a query READS: rows, bytes,
# marks, parts, and the key condition the plan chose. It deliberately does not print the ANSWER.
# So the repo could measure its own latency in detail and had no artifact carrying the numbers
# themselves, while docs/RUNBOOK_UNSEEN_DAY.md step 10 answered the questions with a bare
# PrettyCompact print that wrote nothing, and step 11 then asserted that every step above had
# written a stamped artifact. That assertion was false for exactly one step, which is the step
# whose output is graded.
#
# WHAT THE REVISED PROBLEM STATEMENT ASKS FOR, quoted, because this script is shaped by it:
#   "your system's concurrency results on it -- peak and average concurrency at minute, hour,
#    and day grain, with dimension filters -- along with the query latencies and evidence that
#    they ran through your pipeline."
# Three grains, both statistics, filtered, with latency. All three grains are mandatory, which is
# why GRAINS below is not configurable.
#
# EVERY NUMBER COMES FROM system.query_log, not from a stopwatch around the client. A wall-clock
# measurement here would be measuring the HTTPS round trip to ap-south-1, which is 220-300 ms and
# has nothing to do with the serving layer. Same reasoning, and the same capture loop, as bench.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-${CH_DATABASE:-phoenix_unseen}}"
export CH_DATABASE="$DB"

Q="sql/queries/serving/peak_average.sql"
# The trailing semicolon is stripped because this query gets WRAPPED in an outer aggregate below,
# and `SELECT ... FROM (... ;)` is a syntax error. Costly to find: it made every cell read NA while
# the query itself was perfectly correct.
SQL="$(sed 's/;[[:space:]]*$//' "$Q")"

# THE WINDOW IS THE BUSIEST UTC DAY, not the data's full extent.
#
# Anchored on the data rather than the wall clock, the same rule the consoles follow. But the full
# extent is the wrong default: the unseen day carries a dirty tail spanning 2014 to 2026-08-03, so
# min..max is eleven years wide and `avg_all_minutes` would divide a real audience by ~5.9 million
# empty minutes and report approximately zero. That is a true number answering a worthless
# question.
#
# The busiest day is also what the submission guidelines actually ask for: "at least one full
# window of interest (e.g. a match/event or a day of traffic), with visible peaks and ramps".
# Override with FROM=... TO=... for any other window.
BUSIEST="$(./scripts/ch.sh --format TSVRaw --query "
  SELECT toString(toStartOfDay(minute))
  FROM concurrency_deltas
  WHERE delta > 0
  GROUP BY toStartOfDay(minute)
  ORDER BY sum(delta) DESC
  LIMIT 1" | head -1)"
FROM="${FROM:-$BUSIEST}"
TO="${TO:-$(./scripts/ch.sh --format TSVRaw --query "
  SELECT toString(toDateTime('$BUSIEST') + INTERVAL 1 DAY)" | head -1)}"

# Mandatory per the statement: minute, hour, day.
GRAINS="60 3600 86400"

# The filter shapes. Unfiltered first, then one per dimension, then two combinations, because the
# statement's own worked example is about a combination peaking at a different minute than either
# of its parts. The two content shapes resolve a real content_id out of the data rather than
# hardcoding one that may not exist in a dataset nobody has seen.
TOP_CONTENT="$(./scripts/ch.sh --format TSVRaw --query "
  SELECT toString(content_id) FROM concurrency_deltas
  WHERE delta > 0 GROUP BY content_id ORDER BY sum(delta) DESC LIMIT 1" | head -1)"
TOP_PLATFORM="$(./scripts/ch.sh --format TSVRaw --query "
  SELECT platform FROM concurrency_deltas
  WHERE delta > 0 GROUP BY platform ORDER BY sum(delta) DESC LIMIT 1" | head -1)"
TOP_COUNTRY="$(./scripts/ch.sh --format TSVRaw --query "
  SELECT country FROM concurrency_deltas
  WHERE delta > 0 GROUP BY country ORDER BY sum(delta) DESC LIMIT 1" | head -1)"

# shape_tag | platform | country | video_type | app_version | content_id
SHAPES="
unfiltered|||||0
platform|${TOP_PLATFORM}||||0
country||${TOP_COUNTRY}|||0
content|||||${TOP_CONTENT:-0}
platform+country|${TOP_PLATFORM}|${TOP_COUNTRY}|||0
platform+content|${TOP_PLATFORM}||||${TOP_CONTENT:-0}
"

# Captures one run: the ANSWER from the query, and the LATENCY from query_log for that exact
# query_id. Same flush-inside-the-retry-loop pattern as bench.sh: a single flush fired straight
# after the query can run before the log entry exists, and then nothing flushes again until the
# 7.5s interval elapses, so the capture never converges.
run_one() {  # plat ctry vtype appv cid grain tag -> answer columns + latency columns
  local plat="$1" ctry="$2" vtype="$3" appv="$4" cid="$5" grain="$6" tag="$7"
  local qid="answers_${tag}_${grain}_$$_${RANDOM}" answer="" perf=""

  # The answer. Bucket rows collapse to the extremes across the whole window: the peak of the
  # peaks, and the average weighted by each bucket's own minute count, so a day-grain row and
  # 1,440 minute-grain rows describe the same window rather than disagreeing about it.
  answer="$(./scripts/ch.sh --format TSVRaw --query "
    SELECT toString(max(peak_concurrency)),
           toString(argMax(peak_minute, peak_concurrency)),
           toString(round(sum(avg_all_minutes    * minutes_in_bucket) / nullIf(sum(minutes_in_bucket), 0), 2)),
           toString(round(sum(avg_active_minutes * minutes_with_audience) / nullIf(sum(minutes_with_audience), 0), 2)),
           toString(sum(minutes_with_audience)),
           toString(sum(minutes_in_bucket)),
           toString(count())
    FROM ($SQL)" \
    --param_platform="$plat" --param_country="$ctry" --param_video_type="$vtype" \
    --param_app_version="$appv" --param_content_id="$cid" \
    --param_from_ts="$FROM" --param_to_ts="$TO" --param_grain_s="$grain" \
    --query_id="$qid" 2>/dev/null </dev/null | head -1)"

  if [ -z "$answer" ]; then
    echo "WARNING: no answer for shape=$tag grain=$grain" >&2
    answer=$'NA\tNA\tNA\tNA\tNA\tNA\tNA'
  fi

  for _ in 1 2 3 4 5 6 7 8; do
    ./scripts/ch.sh --query "SYSTEM FLUSH LOGS" >/dev/null 2>&1 </dev/null || true
    perf="$(./scripts/ch.sh --format TSVRaw --query "
      SELECT toString(query_duration_ms), toString(read_rows), toString(read_bytes)
      FROM clusterAllReplicas(default, system.query_log)
      WHERE type = 'QueryFinish' AND query_id = '$qid'" 2>/dev/null </dev/null | head -1)"
    [ -n "$perf" ] && break
    sleep 2
  done
  # NA rather than a zero, so a missing measurement can never be read as a measured zero.
  [ -z "$perf" ] && { echo "WARNING: no query_log row for $qid" >&2; perf=$'NA\tNA\tNA'; }

  printf '%s\t%s' "$answer" "$perf"
}

{
  printf 'shape\tgrain\tpeak_concurrency\tpeak_minute\tavg_all_minutes\tavg_active_minutes\t'
  printf 'minutes_with_audience\tminutes_total\tbuckets\tquery_ms\tread_rows\tread_bytes\tquery_id_prefix\n'

  echo "$SHAPES" | while IFS='|' read -r tag plat ctry vtype appv cid; do
    [ -z "$tag" ] && continue
    for grain in $GRAINS; do
      grain_name=$([ "$grain" = 60 ] && echo minute || { [ "$grain" = 3600 ] && echo hour || echo day; })
      printf '%s\t%s\t%s\tanswers_%s_%s\n' \
        "$tag" "$grain_name" "$(run_one "$plat" "$ctry" "$vtype" "$appv" "${cid:-0}" "$grain" "$tag")" \
        "$tag" "$grain"
    done
  done

  printf '#\n'
  printf '# database\t%s\n' "$DB"
  printf '# window\t%s -> %s\n' "$FROM" "$TO"
  printf '# query\t%s\n' "$Q"
  printf '# grains\tminute (60s), hour (3600s), day (86400s)\n'
  printf '# top_platform\t%s\n' "$TOP_PLATFORM"
  printf '# top_country\t%s\n' "$TOP_COUNTRY"
  printf '# top_content_id\t%s\n' "$TOP_CONTENT"
  printf '# latency_source\tsystem.query_log query_duration_ms, NOT a client-side stopwatch\n'
  printf '# service\t%s\n' "$(./scripts/ch.sh --format TSVRaw --query "SELECT version()" | head -1)"
} | evidence "answers_${DB}" \
    "peak and average concurrency at minute, hour and day grain across filter shapes, with per-query latency from system.query_log" \
  | xargs cat
