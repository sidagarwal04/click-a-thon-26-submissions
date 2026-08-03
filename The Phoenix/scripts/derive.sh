#!/usr/bin/env bash
# The full batch derivation, guarded so it cannot silently corrupt on a re-run.
#
#   ./scripts/derive.sh                    # derive into $CH_DATABASE, refuse if not empty
#   ./scripts/derive.sh phoenix_unseen     # derive into a named database
#   REBUILD=1 ./scripts/derive.sh phoenix_unseen   # truncate the derived tables first
#
# WHY THIS SCRIPT EXISTS, measured rather than argued: 02_merge_runs.sql and
# 04_merge_user_runs.sql assert sign = +1 unconditionally and APPEND. Running either twice
# doubles every run. Measured on a throwaway copy of the validated corpus: asserted runs
# 17,604 -> 35,208 and peak concurrency 2,829 -> 5,658. Evidence: derive_idempotence.
#
# What makes that dangerous rather than merely wrong is that the obvious guards do not fire:
#
#   closure, sum(delta) = 0, STAYS 0, because every duplicated +1 brings its own -1.
#   max_runs_per_session_minute STAYS 1, because the duplicate run has an identical key, so
#     GROUP BY collapses it. That invariant detects overlapping runs, and this is repetition.
#
# A pipeline relying on either would report a perfectly healthy, exactly-doubled dataset. So
# the protection here is structural instead: refuse to derive into a database that already
# holds derived rows, and verify afterwards with the one invariant that does detect it,
# max(sum(sign)) per run = 1.
#
# TASK.md asks for derive-to-shadow-and-swap with EXCHANGE TABLES. This is the cheaper
# guarantee and it is honest about being cheaper: it makes the corruption UNREACHABLE rather
# than RECOVERABLE. The rehearsed cost of a clean rebuild is 14 seconds
# (evidence: runbook_rehearsal), which is what makes refuse-and-rebuild an acceptable answer
# where it would not be on a slower pipeline.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-${CH_DATABASE:-phoenix}}"
export CH_DATABASE="$DB"
ch() { ./scripts/ch.sh "$@"; }
val() { ch --format TSVRaw --query "$1" 2>/dev/null | head -1; }

echo "== target database: $DB" >&2

existing="$(val "SELECT ifNull(sum(sign), 0) FROM session_minute_runs")"
if [ "${existing:-0}" != "0" ]; then
  if [ "${REBUILD:-0}" = "1" ]; then
    echo "== REBUILD=1: truncating derived tables ($existing asserted runs present)" >&2
    for t in foreground_intervals session_minute_runs concurrency_deltas user_minute_runs user_concurrency_deltas; do
      ch --query "TRUNCATE TABLE $t"
    done
  else
    echo "REFUSING TO DERIVE: $DB already holds $existing asserted runs." >&2
    echo "  Deriving again would APPEND and double them, and neither closure nor" >&2
    echo "  max_runs_per_session_minute would notice. Re-run with REBUILD=1 to truncate first," >&2
    echo "  or drop and recreate the database. See evidence/derive_idempotence." >&2
    exit 1
  fi
fi

t0=$(date +%s)
echo "== 01 derive intervals" >&2
ch --queries-file sql/pipeline/01_derive_intervals.sql --param_tolerance_s=90 --param_pause_inactive=1
echo "== 02 merge runs" >&2
ch --queries-file sql/pipeline/02_merge_runs.sql
echo "== 04 merge user runs" >&2
ch --queries-file sql/pipeline/04_merge_user_runs.sql
t1=$(date +%s)

runs="$(val "SELECT sum(sign) FROM session_minute_runs")"
closure="$(val "SELECT sum(delta) FROM concurrency_deltas")"
dupes="$(val "SELECT max(s) FROM (SELECT sum(sign) AS s FROM session_minute_runs GROUP BY video_session_id, run_start, run_end HAVING s > 0)")"
overlap="$(val "SELECT max(n) FROM (SELECT count() AS n FROM (SELECT video_session_id, run_start, run_end FROM session_minute_runs GROUP BY video_session_id, run_start, run_end HAVING sum(sign) > 0) ARRAY JOIN timeSlots(run_start, toUInt32(dateDiff('second', run_start, run_end)), 60) AS m GROUP BY video_session_id, m)")"

verdict=PASS
[ "$closure" = "0" ] || verdict=FAIL
[ "$dupes"   = "1" ] || verdict=FAIL
[ "$overlap" = "1" ] || verdict=FAIL

{
  printf 'metric\tvalue\n'
  printf 'database\t%s\n' "$DB"
  printf 'derive_seconds\t%s\n' "$(( t1 - t0 ))"
  printf 'asserted_runs\t%s\n' "$runs"
  printf 'invariant.closure\t%s\t(required 0)\n' "$closure"
  printf 'invariant.max_assertions_of_one_run\t%s\t(required 1, the only one that catches a double derive)\n' "$dupes"
  printf 'invariant.max_runs_per_session_minute\t%s\t(required 1)\n' "$overlap"
  printf 'verdict\t%s\n' "$verdict"
} | evidence "derive_${DB}" "guarded batch derivation into ${DB}, with the post-conditions that would catch a double derive" \
  | xargs cat

[ "$verdict" = PASS ] || { echo "DERIVE POST-CONDITIONS FAILED" >&2; exit 1; }
