#!/usr/bin/env bash
# Rehearse docs/RUNBOOK_UNSEEN_DAY.md end to end against a throwaway database.
#
#   ./scripts/rehearse_runbook.sh [database] [csv]
#
# A runbook that has never been run is a wish. This runs the real steps against a real
# service with the real CSV, times each one, and writes the timings as evidence so the
# unseen-day estimate is measured rather than guessed.
#
# The target defaults to phoenix_scratch_rehearsal and is DROPPED at the start. It never
# touches phoenix.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-phoenix_scratch_rehearsal}"
CSV="${2:-data/ch-hackathon-raw-data.csv}"
# Peak the rebuild must reproduce. 2,828 since decision D8; it was 2,829 before intervals were
# bounded at the session's last VideoSessionEnd.
EXPECTED_PEAK="${EXPECTED_PEAK:-2828}"
CONTENT="data/ch-hackathon-content-data.csv"
case "$DB" in phoenix|phoenix_live|phoenix_unseen) echo "refusing to rehearse into $DB" >&2; exit 1;; esac
[ -f "$CSV" ] || { echo "no such file: $CSV" >&2; exit 1; }

TIMINGS=""
t_all_start=$(date +%s)
step() {  # step "name" command...
  local name="$1"; shift
  local t0 t1
  echo "== $name" >&2
  t0=$(date +%s)
  "$@" >/dev/null 2>&1 || { echo "STEP FAILED: $name" >&2; TIMINGS="${TIMINGS}${name}\tFAILED\n"; return 1; }
  t1=$(date +%s)
  echo "   $(( t1 - t0 ))s" >&2
  TIMINGS="${TIMINGS}${name}\t$(( t1 - t0 ))\n"
}

./scripts/ch.sh --query "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1

step "1_dry_run_inspect"      ./scripts/load.sh --dry-run "$CSV"
step "2_init_db"              ./scripts/init_db.sh "$DB"
step "3a_load_content"        ./scripts/load.sh "$CONTENT" content            "$DB"
step "3b_load_events"         ./scripts/load.sh "$CSV"     raw_events_landing "$DB"
step "4_vocabulary_check"     env CH_DATABASE="$DB" ./scripts/vocabulary_check.sh "$DB"
step "5a_derive_intervals"    env CH_DATABASE="$DB" ./scripts/ch.sh --queries-file sql/pipeline/01_derive_intervals.sql --param_tolerance_s=90 --param_pause_inactive=1
step "5b_merge_runs"          env CH_DATABASE="$DB" ./scripts/ch.sh --queries-file sql/pipeline/02_merge_runs.sql
step "5c_merge_user_runs"     env CH_DATABASE="$DB" ./scripts/ch.sh --queries-file sql/pipeline/04_merge_user_runs.sql
step "6_ground_state_verify"  env CH_DATABASE="$DB" ./scripts/ground_state.sh
step "8_peak_not_a_rollup"    env CH_DATABASE="$DB" ./scripts/test_peak.sh
step "9_benchmark_set"        env CH_DATABASE="$DB" ./scripts/bench.sh
t_all_end=$(date +%s)

# The rehearsal is only meaningful if the rebuilt database agrees with the validated one, so
# the headline numbers are compared rather than merely produced.
gs="$(env CH_DATABASE="$DB" ./scripts/ground_state.sh 2>/dev/null)"
get() { printf '%s\n' "$gs" | awk -F'\t' -v k="$1" '$1 == k { print $2 }'; }

{
  printf 'step\tseconds\n'
  printf "$TIMINGS"
  printf 'TOTAL_WALL_CLOCK\t%s\n' "$(( t_all_end - t_all_start ))"
  printf '#\n# rebuilt database vs the validated corpus:\n'
  printf 'rebuilt.peak_concurrency\t%s\n'      "$(get serving.peak_concurrency)"
  printf 'rebuilt.peak_minute\t%s\n'           "$(get serving.peak_minute)"
  printf 'rebuilt.minutes_with_audience\t%s\n' "$(get serving.minutes_with_audience)"
  printf 'rebuilt.avg_all_minutes\t%s\n'       "$(get serving.avg_all_minutes)"
  printf 'rebuilt.asserted_runs\t%s\n'         "$(get runs.session_minute_runs.asserted)"
  printf 'rebuilt.closure\t%s\n'               "$(get invariant.closure.session_deltas)"
  printf 'rebuilt.max_runs_per_session_minute\t%s\n' "$(get invariant.max_runs_per_session_minute)"
  # EXPECTED_PEAK is a parameter, not a literal, and the reason is that this gate has already been
  # wrong once for the right reason. It hardcoded 2829, which was correct until decision D8 bounded
  # intervals at the session's last VideoSessionEnd and moved peak to 2828. The rehearsal then
  # reported FAIL while the rebuild was in fact perfect: the pipeline had changed and the gate had
  # not. A gate that fails when the answer legitimately changes trains people to ignore it.
  #
  # So: keep asserting an exact value, because a rebuild that silently produces a different peak is
  # the thing worth catching, but make the expected value visible in the artifact and overridable
  # from the environment, so the next intentional change updates one line instead of being argued
  # with. Whoever changes it should be able to name the decision that moved it.
  printf '#\texpected_peak\t%s\t(override with EXPECTED_PEAK, moved by decision D8)\n' "$EXPECTED_PEAK"
  printf 'verdict\t%s\n' "$( [ "$(get serving.peak_concurrency)" = "$EXPECTED_PEAK" ] && [ "$(get invariant.max_runs_per_session_minute)" = "1" ] && echo PASS || echo FAIL )"
  printf '#\n# database\t%s\n# csv\t%s\n' "$DB" "$CSV"
} | evidence runbook_rehearsal "docs/RUNBOOK_UNSEEN_DAY.md executed end to end on a throwaway database, per-step wall clock" \
  | xargs cat
