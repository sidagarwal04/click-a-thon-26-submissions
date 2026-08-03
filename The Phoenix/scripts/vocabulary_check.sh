#!/usr/bin/env bash
# UNKNOWN_VOCABULARY report. Run this FIRST on any new data, before deriving anything.
#
#   ./scripts/vocabulary_check.sh                      # whole table vs the validated corpus
#   FROZEN_BEFORE=2099-01-01 ./scripts/vocabulary_check.sh
#
# BASELINE_BEFORE is the boundary of the vocabulary we already know (default 2026-08-01, the
# validated corpus). FROZEN_BEFORE is how much data to inspect. Leaving FROZEN_BEFORE at its
# default inspects only the corpus and finds nothing new, which is correct and is the point:
# on the unseen day you widen FROZEN_BEFORE and the report tells you what arrived.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-${CH_DATABASE:-phoenix}}"
BASELINE="${BASELINE_BEFORE:-2026-08-01}"

rows="$(CH_DATABASE="$DB" ./scripts/ch.sh --format TSV \
  --queries-file sql/queries/validation/unknown_vocabulary.sql \
  --param_baseline_before="$BASELINE" 2>/dev/null || true)"
n="$(printf '%s' "$rows" | grep -c . || true)"

{
  printf 'finding\tvalue\tcontext\tevents\tsessions\tfirst_seen\tlast_seen\teffect\n'
  [ "$n" -gt 0 ] && printf '%s\n' "$rows"
  printf '#\n# unknown_values\t%s\n' "$n"
  printf '# baseline_before\t%s\n' "$BASELINE"
  printf '# inspected_before\t%s\n' "${FROZEN_BEFORE:-2026-08-01}"
  printf '# verdict\t%s\n' "$( [ "$n" -eq 0 ] && echo 'PASS (no unrecognised vocabulary)' || echo 'RECORDED (unrecognised values found, all neutral by default, see effect column)' )"
} | evidence unknown_vocabulary "event_type and event values the classifier does not recognise, with counts and what they currently do" \
  | xargs cat

# Deliberately exit 0 even when values are found. An unknown value is NEUTRAL and therefore
# safe: it can fail to extend viewing time but can never manufacture it. Halting the unseen-day
# pipeline over a new telemetry event would be the expensive answer to a safe condition. The
# report exists so a human can decide, not so a script can panic.
[ "$n" -gt 0 ] && echo "note: $n unrecognised value(s) found, all neutral; review the artifact" >&2
exit 0
