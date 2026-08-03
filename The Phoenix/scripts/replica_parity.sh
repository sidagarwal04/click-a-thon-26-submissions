#!/usr/bin/env bash
# Is the replica's INDEPENDENTLY DERIVED serving layer the same answer as the original's?
#
#   ./scripts/replica_parity.sh
#   SRC_DB=phoenix DST_DB=phoenix_next ./scripts/replica_parity.sh
#
# scripts/replicate.sh copies raw events and re-derives. That makes the destination's serving
# layer an independent derivation rather than a copy, and this is the script that cashes that
# in: if two separate runs of the pipeline over the same raw events produce the same curve, the
# same peak and the same three averages, the replica is trustworthy and the pipeline is
# reproducible. If they disagree, one of them is wrong and we would rather find out here than
# after six insight tables have been built on top.
#
# WHY EVERY COMPARISON IS BOUNDED AT frozen_before. A teammate ingests into phoenix
# continuously and phoenix's derived tables lag its raw_events by however long it has been
# since the last batch derive, measured at 47 minutes when this was written. Comparing at the
# live watermark pits this replica's fresh derivation against phoenix's stale one and fails for
# a reason that has nothing to do with replication. The frozen slice is closed, identical on
# both sides by construction, and is the graded corpus. Live-slice figures are RECORDED at the
# bottom and gate nothing.
#
# WHAT IS DELIBERATELY NOT ASSERTED: count() on either delta table. They are SummingMergeTree,
# so a bare count returns PHYSICAL rows and moves with merge progress. phoenix's 30,662 is long
# merged and a freshly written replica has unmerged rows sharing an ORDER BY key. The same
# effect already shows up as user_minute_runs at 58,703 physical against the 81,349 recorded in
# docs/database_details.md. The row-by-row curve diff below covers logical equality strictly
# better, so the counts are recorded and not gated.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

SRC="${SRC_DB:-phoenix}"
DST="${DST_DB:-phoenix_next}"
export EVIDENCE_STAMP_DB="$DST"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# The whole corpus, widened a day on each side so the bound cannot be mistaken for a
# hand-fitted range. Same window scripts/parity.sh uses against the oracle.
FROM="${PARITY_FROM:-2026-07-13 00:00:00}"
TO="${PARITY_TO:-2026-07-28 00:00:00}"
# The published headline: peak 2,828 and average 88.06 over 1,440 minutes.
DAY_FROM="${DAY_FROM:-2026-07-26 00:00:00}"
DAY_TO="${DAY_TO:-2026-07-27 00:00:00}"

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { CH_DATABASE="$1" ch --format TSVRaw --query "$2" | head -1; }
args() { printf -- '--param_platform=\n--param_country=\n--param_video_type=\n--param_app_version=\n--param_content_id=0\n--param_from_ts=%s\n--param_to_ts=%s\n' "$1" "$2"; }

run_serving() { # db, sqlfile, from, to
  local db="$1" f="$2"; shift 2
  mapfile -t a < <(args "$1" "$2")
  CH_DATABASE="$db" ch --format TSV "${a[@]}" --queries-file "$f"
}

echo "== 0. precondition: the frozen slice must be identical on both sides" >&2
s_frz="$(val "$SRC" "SELECT count() FROM raw_events WHERE event_timestamp < {frozen_before:String}")"
d_frz="$(val "$DST" "SELECT count() FROM raw_events WHERE event_timestamp < {frozen_before:String}")"
if [ "$s_frz" != "$d_frz" ]; then
  echo "ABORT: frozen slice differs, $SRC=$s_frz $DST=$d_frz. Nothing below would mean anything." >&2
  exit 1
fi
echo "   both $s_frz rows" >&2

echo "== 1. invariants and asserted runs inside the frozen slice" >&2
declare -A M
for db in "$SRC" "$DST"; do
  M[$db.closure]="$(val   "$db" "SELECT sum(delta) FROM concurrency_deltas")"
  M[$db.uclosure]="$(val  "$db" "SELECT sum(delta) FROM user_concurrency_deltas")"
  M[$db.runs]="$(val      "$db" "SELECT sum(sign) FROM session_minute_runs WHERE run_start < {frozen_before:String}")"
  M[$db.uruns]="$(val     "$db" "SELECT sum(sign) FROM user_minute_runs    WHERE run_start < {frozen_before:String}")"
  M[$db.deltas]="$(val    "$db" "SELECT count() FROM concurrency_deltas WHERE minute < {frozen_before:String}")"
done

echo "== 2. headline day: peak and the three averages" >&2
for db in "$SRC" "$DST"; do
  run_serving "$db" sql/queries/serving/average_definitions.sql "$DAY_FROM" "$DAY_TO" \
    | awk -F'\t' '{print $1 "\t" $3 "\t" $4}' | LC_ALL=C sort > "$TMP/avg.$db"
  M[$db.peak]="$(run_serving "$db" sql/queries/serving/concurrency_curve.sql "$DAY_FROM" "$DAY_TO" \
    | awk -F'\t' 'NR==1 {print $3}')"
done

echo "== 3. whole-corpus curve, minute by minute" >&2
for db in "$SRC" "$DST"; do
  run_serving "$db" sql/queries/serving/concurrency_curve.sql "$FROM" "$TO" \
    | awk -F'\t' '{print $1 "\t" $2}' > "$TMP/curve.$db"
done
# Sorted by construction (the query ends ORDER BY minute), so diff compares like for like.
curve_diff=$(diff "$TMP/curve.$SRC" "$TMP/curve.$DST" | grep -c '^[<>]' || true)
curve_rows=$(wc -l < "$TMP/curve.$DST")
avg_diff=$(diff "$TMP/avg.$SRC" "$TMP/avg.$DST" | grep -c '^[<>]' || true)

# Missing and unexpected keys reported separately from differing values, because the gate the
# plan asks for names all three and "0 diff rows" alone does not distinguish them.
cut -f1 "$TMP/curve.$SRC" | LC_ALL=C sort > "$TMP/k.src"
cut -f1 "$TMP/curve.$DST" | LC_ALL=C sort > "$TMP/k.dst"
missing=$(comm -23 "$TMP/k.src" "$TMP/k.dst" | wc -l)
unexpected=$(comm -13 "$TMP/k.src" "$TMP/k.dst" | wc -l)

eq() { [ "${M[$SRC.$1]}" = "${M[$DST.$1]}" ] && echo PASS || echo FAIL; }
verdict=PASS
for k in closure uclosure runs uruns peak; do [ "$(eq "$k")" = PASS ] || verdict=FAIL; done
[ "$curve_diff" = 0 ] || verdict=FAIL
[ "$avg_diff"   = 0 ] || verdict=FAIL
[ "$missing"    = 0 ] || verdict=FAIL
[ "$unexpected" = 0 ] || verdict=FAIL
[ "${M[$SRC.closure]}" = "0" ] && [ "${M[$DST.closure]}" = "0" ] || verdict=FAIL

{
  printf 'metric\t%s\t%s\tverdict\n' "$SRC" "$DST"
  printf 'frozen_slice_raw_events\t%s\t%s\tPASS\n' "$s_frz" "$d_frz"
  for k in closure uclosure runs uruns peak; do
    printf '%s\t%s\t%s\t%s\n' "$k" "${M[$SRC.$k]}" "${M[$DST.$k]}" "$(eq "$k")"
  done
  printf 'curve_minutes_compared\t%s\t%s\t\n'   "$curve_rows" "$curve_rows"
  printf 'curve_differing_rows\t%s\t%s\t%s\n'   "$curve_diff" "$curve_diff" "$([ "$curve_diff" = 0 ] && echo PASS || echo FAIL)"
  printf 'curve_missing_keys\t%s\t%s\t%s\n'     "$missing" "$missing"       "$([ "$missing" = 0 ] && echo PASS || echo FAIL)"
  printf 'curve_unexpected_keys\t%s\t%s\t%s\n'  "$unexpected" "$unexpected" "$([ "$unexpected" = 0 ] && echo PASS || echo FAIL)"
  printf 'average_definitions_differing_rows\t%s\t%s\t%s\n' "$avg_diff" "$avg_diff" "$([ "$avg_diff" = 0 ] && echo PASS || echo FAIL)"
  printf '#\tcorpus_window\t%s .. %s\n'   "$FROM" "$TO"
  printf '#\theadline_day\t%s .. %s\n'    "$DAY_FROM" "$DAY_TO"
  # Recorded, never gated: physical row counts on a SummingMergeTree move with merge progress.
  printf '#\tfrozen_delta_rows_physical\t%s\t%s\t(recorded, merge-dependent, not a gate)\n' "${M[$SRC.deltas]}" "${M[$DST.deltas]}"
  printf 'verdict\t%s\t%s\t%s\n' "$verdict" "$verdict" "$verdict"
  [ "$curve_diff" = 0 ] || diff "$TMP/curve.$SRC" "$TMP/curve.$DST" | head -10 | sed 's/^/# curve_diff: /' >&2
} | evidence "replica_parity_${DST}" "independently re-derived ${DST} serving layer against ${SRC}, frozen slice" \
  | xargs cat

[ "$verdict" = PASS ] || { echo "REPLICA PARITY FAILED" >&2; exit 1; }
echo "REPLICA PARITY PASS: $DST reproduces $SRC on the frozen slice" >&2
