#!/usr/bin/env bash
# Assert that peak concurrency cannot be derived from a per-dimension rollup.
#
#   ./scripts/test_peak.sh
#
# Exits non-zero if any assertion fails. Storing a peak per rollup level is the obvious
# optimisation and it is wrong, so this is the regression test that would catch someone
# making it later. See sql/queries/serving/test_peak_is_not_a_rollup.sql for the reasoning.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

out="$(./scripts/ch.sh --queries-file sql/queries/serving/test_peak_is_not_a_rollup.sql --format TSV 2>/dev/null)"
fails="$(printf '%s\n' "$out" | awk -F'\t' '$3 == "FAIL"' | wc -l)"
total="$(printf '%s\n' "$out" | grep -c . || true)"

{
  printf 'assertion\tobserved\tverdict\n'
  printf '%s\n' "$out"
  printf '#\n# assertions\t%s\n# failures\t%s\n' "$total" "$fails"
} | evidence peak_not_a_rollup "peak minutes differ across filter tuples, and the overall peak is neither the max nor the sum of per-platform peaks" \
  | xargs cat

if [ "$fails" -ne 0 ]; then
  echo "PEAK TEST FAILED: $fails of $total assertions" >&2
  exit 1
fi
echo "peak test: $total of $total assertions PASS" >&2
