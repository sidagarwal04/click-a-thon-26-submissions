#!/usr/bin/env bash
# Ground truth against the serving table, one insight at a time, zero diffs required.
#
#   ./scripts/validate_insights.sh                 # every insight
#   ./scripts/validate_insights.sh session_facts   # one
#
# WHY THE DIFF IS A SCRIPT AND NOT A <name>_diff.sql FILE, which is what the plan asks for. The
# two sides live in different engines on purpose: the ground truth runs in `clickhouse local`
# over the raw CSV, the optimized side runs on Cloud. No single SQL statement spans them, and
# making one would mean giving up the second engine, which is most of what the comparison is
# worth. scripts/parity.sh already made this trade for the concurrency oracle. Both SIDES are
# committed SQL; only the subtraction is bash.
#
# Missing and unexpected keys are reported separately from differing values, because "0 diff
# rows" hides the difference between a wrong number and an absent session.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
export CH_DATABASE="$DB" EVIDENCE_STAMP_DB="$DB"
CSV="${RAW_CSV:-data/ch-hackathon-raw-data.csv}"
ONLY="${1:-}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

fail_any=0

POS='--param_platform= --param_country= --param_video_type= --param_app_version=
     --param_content_id=0'

# Self-contained server-side diff. Empty output is the pass, which is also exactly what a
# comparison that never happened looks like, so the two sides are counted separately and both are
# required to be non-empty before an empty diff is allowed to mean anything. This repo already has
# a file listing eleven numbers that were plausible and unchecked; a green check that checked
# nothing is the failure mode worth spending ten lines on.
validate_selfdiff() {
  local name="$1" diff_sql="$2"
  local gt="sql/insights/validation/${name}_ground_truth.sql"
  local op="sql/insights/benchmark/${name}.sql"
  local from="${FROM_TS:-2026-07-26 00:00:00}" to="${TO_TS:-2026-07-27 00:00:00}"
  local frozen="${FROZEN_BEFORE:-2026-08-01}"

  run() { # queries-file -> TSV on stdout
    # shellcheck disable=SC2086
    ./scripts/ch.sh --format TSV $POS \
      --param_from_ts="$from" --param_to_ts="$to" --param_frozen_before="$frozen" \
      --queries-file "$1" 2>/dev/null </dev/null
  }

  echo "== $name: server-side diff on $DB" >&2
  local differing gt_rows op_rows verdict=PASS
  differing=$(run "$diff_sql" | grep -c . || true)
  gt_rows=$([ -f "$gt" ] && run "$gt" | grep -c . || echo 0)
  op_rows=$(run "$op" | grep -c . || true)

  [ "$differing" = 0 ] || { verdict=FAIL; fail_any=1; }
  { [ "${gt_rows:-0}" -gt 0 ] && [ "${op_rows:-0}" -gt 0 ]; } || { verdict=FAIL; fail_any=1; }

  {
    printf 'metric\tvalue\n'
    printf 'insight\t%s\n'  "$name"
    printf 'database\t%s\n' "$DB"
    printf 'reference_kind\tserver-side diff: %s (both sides embedded, one statement)\n' "$diff_sql"
    printf 'window\t%s -> %s (frozen_before %s)\n' "$from" "$to" "$frozen"
    printf 'ground_truth_rows\t%s\t(required greater than 0)\n' "$gt_rows"
    printf 'optimized_rows\t%s\t(required greater than 0)\n'    "$op_rows"
    printf 'differing_rows\t%s\t(required 0)\n'                 "$differing"
    printf 'missing_keys\t0\t(the diff reports a missing key as a differing row, with a side column)\n'
    printf 'unexpected_keys\t0\t(same)\n'
    printf 'verdict\t%s\n' "$verdict"
    [ "$differing" = 0 ] || run "$diff_sql" | head -6 | sed 's/^/# diff: /'
  } | evidence "insight_parity_${name}" \
      "${name}: Gate A, ${diff_sql} returns zero disagreements against the ${DB} serving table" \
    | xargs cat
}

validate() {
  local name="$1"
  local gt="sql/insights/validation/${name}_ground_truth.sql"
  local ref="sql/insights/validation/${name}_reference.sql"
  local op="sql/insights/validation/${name}_optimized.sql"
  local selfdiff="sql/insights/validation/${name}_diff.sql"
  # A THIRD SHAPE: the whole subtraction in one server-side file. Both sides read the same
  # database, so unlike the two-engine form there is nothing for bash to join, and the file
  # returns one row per disagreement and nothing at all when they agree.
  [ -f "$op" ] || { [ -f "$selfdiff" ] && { validate_selfdiff "$name" "$selfdiff"; return $?; }
                    echo "skip $name: no optimized side" >&2; return 0; }

  # TWO KINDS OF REFERENCE, and which one a given insight gets is a real distinction rather than
  # a convenience.
  #
  #   _ground_truth.sql  runs in `clickhouse local` over the raw CSV, with its own copy of the
  #                      state machine. Two engines, two implementations. This is the strong
  #                      form and it is what session_facts gets.
  #
  #   _reference.sql     runs on the server against an ALREADY VALIDATED table. Weaker, because
  #                      it shares an engine and a derivation, and it is the right form when the
  #                      plan's gate names a specific existing table as the authority. The
  #                      audience snapshot's gate is literally "concurrent_sessions must equal
  #                      the authoritative concurrency_deltas curve", and concurrency_deltas is
  #                      itself already proven against the brute-force oracle at zero diffs
  #                      [V:oracle_parity]. Chaining is legitimate; pretending it is the same
  #                      strength as the two-engine form is not, so the artifact records which
  #                      one ran.
  local mode
  if [ -f "$gt" ]; then
    mode="clickhouse local over $CSV, independent implementation"
    echo "== $name: ground truth over $CSV in clickhouse local" >&2
    FORMAT=TSV ./scripts/oracle.sh "$CSV" "$gt" 2>/dev/null | LC_ALL=C sort > "$TMP/gt"
  elif [ -f "$ref" ]; then
    mode="server-side reference: $ref (already-validated table)"
    echo "== $name: reference query on $DB" >&2
    # tolerance_s passed to both sides: a reference that re-derives a timeout must use the
    # same gap the pipeline used, or it disagrees over a configuration rather than a bug.
    ./scripts/ch.sh --format TSV --param_tolerance_s="${TOLERANCE_S:-90}" \
      --queries-file "$ref" 2>/dev/null | LC_ALL=C sort > "$TMP/gt"
  else
    echo "skip $name: no reference of either kind" >&2; return 0
  fi

  echo "== $name: optimized over $DB" >&2
  ./scripts/ch.sh --format TSV --param_tolerance_s="${TOLERANCE_S:-90}" \
    --queries-file "$op" 2>/dev/null | LC_ALL=C sort > "$TMP/op"

  cut -f1 "$TMP/gt" > "$TMP/kgt"
  cut -f1 "$TMP/op" > "$TMP/kop"
  local missing unexpected differing gt_rows op_rows
  missing=$(comm -23 "$TMP/kgt" "$TMP/kop" | wc -l)
  unexpected=$(comm -13 "$TMP/kgt" "$TMP/kop" | wc -l)
  # Value differences on the keys BOTH sides carry, so a missing key is not also counted twice
  # as two differing rows.
  comm -12 "$TMP/kgt" "$TMP/kop" > "$TMP/common"
  LC_ALL=C join -t"$(printf '\t')" "$TMP/common" "$TMP/gt" > "$TMP/gtc"
  LC_ALL=C join -t"$(printf '\t')" "$TMP/common" "$TMP/op" > "$TMP/opc"
  differing=$(diff "$TMP/gtc" "$TMP/opc" | grep -c '^<' || true)
  gt_rows=$(wc -l < "$TMP/gt"); op_rows=$(wc -l < "$TMP/op")

  # ANTI-VACUOUS-PASS. Everything above reports zero when the comparison never happened: an
  # empty join, a key column that did not line up, a query that returned nothing. Zero diffs
  # over zero rows is the shape of a green check that checked nothing, and this repo has a file
  # listing eleven numbers that were plausible and unchecked. So the count of rows actually
  # compared is asserted against the count of keys both sides carry, and the pair is required to
  # be non-empty.
  local common compared columns
  common=$(wc -l < "$TMP/common")
  compared=$(wc -l < "$TMP/gtc")
  columns=$(head -1 "$TMP/gt" | awk -F'\t' '{print NF}')

  local verdict=PASS
  [ "$missing" = 0 ] && [ "$unexpected" = 0 ] && [ "$differing" = 0 ] || { verdict=FAIL; fail_any=1; }
  [ "$compared" = "$common" ] && [ "${compared:-0}" -gt 0 ] || { verdict=FAIL; fail_any=1; }
  [ "${columns:-0}" -gt 1 ] || { verdict=FAIL; fail_any=1; }

  {
    printf 'metric\tvalue\n'
    printf 'insight\t%s\n'                     "$name"
    printf 'database\t%s\n'                    "$DB"
    printf 'reference_kind\t%s\n' "$mode"
    printf 'ground_truth_rows\t%s\n'           "$gt_rows"
    printf 'optimized_rows\t%s\t(frozen slice: sessions whose every event precedes frozen_before)\n' "$op_rows"
    printf 'differing_rows\t%s\t(required 0)\n'    "$differing"
    printf 'missing_keys\t%s\t(required 0)\n'      "$missing"
    printf 'unexpected_keys\t%s\t(required 0)\n'   "$unexpected"
    printf 'keys_in_common\t%s\n'                  "$common"
    printf 'rows_actually_compared\t%s\t(required equal to keys_in_common and greater than 0)\n' "$compared"
    printf 'columns_compared\t%s\t(required greater than 1)\n' "$columns"
    printf 'verdict\t%s\n' "$verdict"
    [ "$missing"    = 0 ] || comm -23 "$TMP/kgt" "$TMP/kop" | head -5 | sed 's/^/# missing: /'
    [ "$unexpected" = 0 ] || comm -13 "$TMP/kgt" "$TMP/kop" | head -5 | sed 's/^/# unexpected: /'
    [ "$differing"  = 0 ] || diff "$TMP/gtc" "$TMP/opc" | head -6 | sed 's/^/# diff: /'
  } | evidence "insight_parity_${name}" "${name}: independent ground truth in clickhouse local against the ${DB} serving table" \
    | xargs cat
}

if [ -n "$ONLY" ]; then
  validate "$ONLY"
else
  found=0
  for gt in sql/insights/validation/*_optimized.sql; do
    [ -e "$gt" ] || break
    found=1
    validate "$(basename "$gt" _optimized.sql)"
  done
  [ "$found" = 1 ] || echo "no insight validation pairs yet" >&2
fi

[ "$fail_any" = 0 ] || { echo "INSIGHT VALIDATION FAILED" >&2; exit 1; }
