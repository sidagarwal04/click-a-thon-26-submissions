#!/usr/bin/env bash
# Phase 1 gate: prove the frozen slice is stable while live ingest is running.
#
#   ./scripts/frozen_gate.sh [settle_seconds]
#
# Runs the frozen-slice metric set twice with a gap in between, and diffs. Live ingest is
# writing into phoenix.raw_events the whole time, so if the isolation predicate leaks, the
# two runs disagree and this exits 1.
#
# This is the deliverable that lets every later number mean something. Without it, "peak is
# 2,829" is a measurement of whatever happened to be in the table at the moment somebody
# looked, and re-running it tomorrow quietly produces a different answer with no signal that
# anything changed. That is precisely how three of four published headline numbers in this
# repo ended up wrong.
#
# Note what is NOT compared: the evidence header block. It carries run_utc and the live
# row_count, which are supposed to differ between two runs. Comparing them would fail the
# gate for the one reason that proves the gate is working. The payload is the claim.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

SETTLE="${1:-45}"
FROZEN="${FROZEN_BEFORE:-2026-08-01}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "run 1 of 2 (frozen_before=$FROZEN)" >&2
./scripts/ground_state.sh > "$TMP/run1.tsv"

# Watermarks around the pause: the gate is only meaningful if ingest actually moved. If the
# stream is idle, two identical runs prove nothing, and the artifact says so rather than
# claiming a pass it did not earn.
before="$(./scripts/ch.sh --format TSVRaw --query "SELECT count() FROM raw_events" | head -1)"
echo "waiting ${SETTLE}s with ingest live" >&2
sleep "$SETTLE"
after="$(./scripts/ch.sh --format TSVRaw --query "SELECT count() FROM raw_events" | head -1)"

echo "run 2 of 2" >&2
./scripts/ground_state.sh > "$TMP/run2.tsv"

diff_rows="$(diff "$TMP/run1.tsv" "$TMP/run2.tsv" | grep -c '^[<>]' || true)"
arrived=$(( after - before ))

if [ "$diff_rows" -eq 0 ] && [ "$arrived" -gt 0 ]; then
  verdict=PASS
elif [ "$diff_rows" -eq 0 ]; then
  verdict=PASS_BUT_INGEST_IDLE     # stable, but the run did not exercise what it claims to
else
  verdict=FAIL
fi

{
  printf 'metric\tvalue\n'
  printf 'frozen_before\t%s\n' "$FROZEN"
  printf 'settle_seconds\t%s\n' "$SETTLE"
  printf 'raw_events_before\t%s\n' "$before"
  printf 'raw_events_after\t%s\n' "$after"
  printf 'rows_ingested_between_runs\t%s\n' "$arrived"
  printf 'metrics_compared\t%s\n' "$(grep -c . "$TMP/run1.tsv")"
  printf 'differing_lines\t%s\n' "$diff_rows"
  printf 'verdict\t%s\n' "$verdict"
  [ "$diff_rows" -eq 0 ] || { printf '#\n# differences:\n'; diff "$TMP/run1.tsv" "$TMP/run2.tsv" | sed 's/^/# /'; }
  printf '#\n# run 1 payload, verbatim:\n'
  sed 's/^/# /' "$TMP/run1.tsv"
} | evidence frozen_slice_stability \
      "frozen-slice metric set run twice with live ingest in between; identical means the isolation predicate holds" \
  | xargs cat

[ "$verdict" = FAIL ] && { echo "FROZEN SLICE GATE FAILED: the isolation predicate leaks" >&2; exit 1; }
exit 0
