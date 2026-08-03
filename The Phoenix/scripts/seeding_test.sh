#!/usr/bin/env bash
# Does read volume scale with the WIDTH of the requested window, or with the POSITION of its end?
#
#   ./scripts/seeding_test.sh
#
# WHY THE PREVIOUS VERSION OF THIS TEST PROVED NOTHING. It compared a 1-hour window against the
# whole corpus and reported that both read identical rows, concluding that nothing prunes. But the
# 1-hour window was at the END of the corpus, so both queries shared the same upper bound. A
# cumulative sum must be seeded by every delta before the window, so both legitimately had to read
# everything before that shared bound, and identical reads was a tautology rather than a measurement.
#
# The fix is a window at the START of the corpus, which has a genuinely different upper bound.
#
# AND THE FRAMING WAS WRONG TOO. "Nothing prunes, therefore correct" is not a pass: it would mean
# every query pays worst case unconditionally, and what our queries read is a named judging
# criterion. The property actually worth demonstrating is:
#
#   READ VOLUME SCALES WITH THE POSITION OF THE RANGE END, AND NEVER WITH THE WIDTH OF THE WINDOW.
#
# That is the honest claim for this design. It is a consequence of the cumulative sum needing the
# whole prefix, combined with serving/concurrency_curve.sql pushing `minute < to_ts` into the
# filtered CTE, which is a genuine read reduction: deltas at or after to_ts cannot affect a prefix
# sum evaluated before to_ts.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

Q="sql/queries/serving/concurrency_curve.sql"
SQL="$(cat "$Q")"

# Corpus bounds, read rather than assumed.
FIRST="$(./scripts/ch.sh --format TSVRaw --query "SELECT min(minute) FROM concurrency_deltas WHERE minute < {frozen_before:String}" 2>/dev/null | head -1)"
LAST="$(./scripts/ch.sh --format TSVRaw  --query "SELECT max(minute) FROM concurrency_deltas WHERE minute < {frozen_before:String}" 2>/dev/null | head -1)"

# Epoch arithmetic, NOT `date -d "$TS + 1 hour"`. GNU date parses the "+ 1" in that string as a
# UTC OFFSET rather than an interval, so it silently returns the original timestamp: the first run
# of this script produced a zero-width window and a single row of output. Converting to epoch,
# adding seconds, and converting back cannot be misread.
shift_ts() {  # "YYYY-MM-DD HH:MM:SS" seconds -> shifted timestamp
  date -u -d "@$(( $(date -u -d "$1 UTC" +%s) + $2 ))" '+%Y-%m-%d %H:%M:%S'
}

# read_rows comes from system.query_log by exact query_id, never by "most recent row mentioning the
# table": that races with concurrent activity and returns blanks. Same approach as bench.sh, and the
# same reason it passes SQL inline via --query rather than --queries-file, which lands in query_log
# with an empty query_id.
measure() {  # from to label -> "label<TAB>from<TAB>to<TAB>width_min<TAB>read_rows<TAB>read_bytes<TAB>ms"
  local from="$1" to="$2" label="$3"
  local qid="seed_${label}_$$_${RANDOM}" row=""
  ./scripts/ch.sh --query "$SQL" --query_id "$qid" \
    --param_platform '' --param_country '' --param_video_type '' --param_app_version '' \
    --param_content_id 0 --param_from_ts "$from" --param_to_ts "$to" >/dev/null 2>&1
  ./scripts/ch.sh --query "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6; do
    row="$(./scripts/ch.sh --format TSVRaw --query "
      SELECT read_rows, read_bytes, query_duration_ms
      FROM clusterAllReplicas(default, system.query_log)
      WHERE query_id = '$qid' AND type = 'QueryFinish' LIMIT 1" 2>/dev/null | head -1)"
    [ -n "$row" ] && break
    ./scripts/ch.sh --query "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  done
  printf '%s\t%s\t%s\t%s\t%s\n' "$label" "$from" "$to" \
    "$(( ( $(date -u -d "$to UTC" +%s) - $(date -u -d "$from UTC" +%s) ) / 60 ))" "${row:-NA}"
}

{
  printf 'window\tfrom_ts\tto_ts\twidth_minutes\tread_rows\tread_bytes\tquery_ms\n'
  # 1 hour at the START of the corpus. Narrow window, EARLY upper bound.
  measure "$FIRST" "$(shift_ts "$FIRST" 3600)" start_1h
  # 1 hour at the END of the corpus. Same width, LATE upper bound. This is the one the old test used.
  measure "$(shift_ts "$LAST" -3600)" "$LAST" end_1h
  # The whole corpus. Widest window, same late upper bound as end_1h.
  measure "$FIRST" "$LAST" whole_corpus
  printf '#\n'
  printf '#\tcorpus_first_minute\t%s\n' "$FIRST"
  printf '#\tcorpus_last_minute\t%s\n'  "$LAST"
  printf '#\tquery\t%s\n' "$Q"
  printf '#\n'
  printf '#\tMEASURED CONCLUSION, and it contradicts the property this test was written to confirm.\n'
  printf '#\n'
  printf '#\tThe hypothesis was: read volume scales with the POSITION of to_ts and never with the\n'
  printf '#\tWIDTH of the window. Measured, read_rows is IDENTICAL across all three windows at the\n'
  printf '#\tfull delta table. It scales with NEITHER position nor width. The hypothesis is false\n'
  printf '#\tfor rows and true only for read_bytes, which does track the position of to_ts.\n'
  printf '#\n'
  printf '#\tWhy: `minute` is the LAST column of the ORDER BY, deliberately, so that a time predicate\n'
  printf '#\tcannot prune the prefix a cumulative sum needs. That choice is what makes the curve\n'
  printf '#\tcorrect for a window opening mid-stream, and its unavoidable price is that no time\n'
  printf '#\tpredicate prunes GRANULES either. The `minute < to_ts` push-down reduces bytes\n'
  printf '#\tdecompressed, not rows scanned.\n'
  printf '#\n'
  printf '#\tThe honest statement of this design is therefore: READ VOLUME SCALES WITH THE SIZE OF\n'
  printf '#\tTHE CORPUS, and only a DIMENSION filter reduces it (platform prunes to 16,384 rows of\n'
  printf '#\t30,662, evidence: filter_shapes). That is a real scaling limit, not a pass, and it is\n'
  printf '#\texactly what makes the 100x question a day-boundary-snapshot question.\n'
  printf '#\n'
  printf '#\tWhat the old test got right by accident: reads really are equal for end_1h and\n'
  printf '#\twhole_corpus. What it got wrong was concluding anything from that, because it compared\n'
  printf '#\ttwo windows sharing an upper bound and never varied the thing it claimed to test.\n'
} | evidence seeding_position "read volume against window position and window width, three windows, two of them sharing an upper bound" | xargs cat
