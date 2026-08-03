#!/usr/bin/env bash
# Does a live database still match the DDL in sql/schema/?
#
#   ./scripts/schema_drift.sh                 # $CH_DATABASE, then phoenix
#   ./scripts/schema_drift.sh phoenix_next
#   DRIFT_ALLOW='raw_events.arrival_timestamp' ./scripts/schema_drift.sh phoenix
#
# WHY THIS EXISTS, and it is not hypothetical. phoenix.session_minute_runs was found carrying
# INDEX idx_run_range (run_start, run_end) TYPE minmax GRANULARITY 4. Nothing in the repo
# created it, so it arrived by an out-of-band ALTER. That made rebuild_swap.sh a live hazard:
# it builds the shadow from sql/schema/ and then EXCHANGEs the tables into phoenix, so the
# next rebuild would have deleted the index from production and the shadow verify (closure,
# overshoot, row counts) would have passed anyway. It also falsified a sentence in
# docs/database_details.md that a human had written and nothing checked.
#
# HOW IT COMPARES, and why not by normalising SHOW CREATE TABLE. On Cloud the server rewrites
# what you wrote: MergeTree becomes SharedMergeTree with ZooKeeper path arguments,
# `run_end + INTERVAL 1 MINUTE` becomes toIntervalMinute(1), MVs come back with an explicit
# column list. Normalising that text by hand is a pile of regexes that each one is a place to
# be wrong. So instead this applies sql/schema/ to an EMPTY reference database and diffs the
# two through system.columns / system.data_skipping_indices / system.projections /
# system.tables. Both sides go through the identical server rewrite, so the rewrite cancels
# and only real differences survive. The reference is empty, so it costs nothing.
#
# DRIFT_ALLOW is a COMMA-separated list of substrings matched against each diff line with tabs
# rendered as single spaces, so a pattern can span columns. It exists for exactly one thing:
# phoenix is generation 1 and has no arrival_timestamp, phoenix_next is generation 2 and does.
# That gap is deliberate, phoenix is never migrated to close it, and sql/schema/ describes
# generation 2. So phoenix runs with:
#
#   DRIFT_ALLOW='arrival_timestamp,mv_body raw_events_mv'
#
# and phoenix_next runs with NO allowlist and must come back clean. Be honest about what the
# second pattern costs: it silences every difference in that one materialized view's body in
# phoenix, not just the arrival_timestamp one, because the generation-1 side of that diff line
# does not mention the column at all. phoenix_next, the database this project now builds on,
# has no such hole.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

TARGET="${1:-${CH_DATABASE:-phoenix}}"
REF="${REF_DB:-phoenix_schema_ref}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }

# Every structural fact worth comparing, as one sorted TSV per database. The database name is
# the one thing that legitimately differs, so it is never selected.
dump() {
  local db="$1" out="$2"
  {
    CH_DATABASE="$db" ch --format TSVRaw --query "
      SELECT 'table', name, engine, sorting_key, partition_key, primary_key, sampling_key
      FROM system.tables WHERE database = currentDatabase()"
    CH_DATABASE="$db" ch --format TSVRaw --query "
      SELECT 'column', table, name, type, default_kind, default_expression, compression_codec
      FROM system.columns WHERE database = currentDatabase()"
    CH_DATABASE="$db" ch --format TSVRaw --query "
      SELECT 'index', table, name, type_full, expr, toString(granularity)
      FROM system.data_skipping_indices WHERE database = currentDatabase()"
    CH_DATABASE="$db" ch --format TSVRaw --query "
      SELECT 'projection', table, name, type, sorting_key
      FROM system.projections WHERE database = currentDatabase()"
    # An MV whose SELECT changed is drift that no column comparison can see: the target table
    # keeps its shape while the rows going into it change meaning. UUIDs and the database name
    # are the only legitimate per-database differences, so both are erased.
    CH_DATABASE="$db" ch --format TSVRaw --query "
      SELECT 'mv_body', name,
             replaceRegexpAll(
               replaceAll(create_table_query, currentDatabase() || '.', 'DB.'),
               'UUID \'[0-9a-f-]+\'', 'UUID')
      FROM system.tables WHERE database = currentDatabase() AND engine = 'MaterializedView'"
  } | LC_ALL=C sort > "$out"
}

# A database is one layer or two. phoenix is the concurrency engine alone; phoenix_next also
# carries the insight layer from sql/insights/schema/. Stated per call rather than sniffed from
# the target, because a detector that infers what it is supposed to find will always agree with
# whatever it finds.
LAYERS="sql/schema/"
[ "${INSIGHTS:-0}" = "1" ] && LAYERS="$LAYERS + sql/insights/schema/"

echo "== reference database $REF, built from $LAYERS and left empty" >&2
ch --query "DROP DATABASE IF EXISTS $REF"
./scripts/init_db.sh "$REF" >/dev/null
[ "${INSIGHTS:-0}" = "1" ] && ./scripts/init_insights.sh "$REF" >/dev/null

echo "== dumping structure: $REF and $TARGET" >&2
dump "$REF"    "$TMP/ref.tsv"
dump "$TARGET" "$TMP/target.tsv"

# `<` is in the repo and missing from the server, `>` is on the server and missing from the
# repo. The second kind is what an out-of-band ALTER looks like.
diff "$TMP/ref.tsv" "$TMP/target.tsv" | grep '^[<>]' > "$TMP/raw_diff" || true

: > "$TMP/diff"
: > "$TMP/allowed"
while IFS= read -r line; do
  # Tabs rendered as spaces so a pattern can span columns.
  flat="$(printf '%s' "$line" | tr '\t' ' ')"
  matched=""
  # Comma-separated, not whitespace-separated: a pattern must be able to contain spaces.
  while IFS= read -r pat; do
    [ -z "$pat" ] && continue
    case "$flat" in *"$pat"*) matched=1; break ;; esac
    # printf '%s\n', not '%s': without the trailing newline `read` returns non-zero on the
    # final element and the LAST pattern in the list is silently never tested.
  done < <(printf '%s\n' "${DRIFT_ALLOW:-}" | tr ',' '\n')
  [ -n "$matched" ] && printf '%s\n' "$line" >> "$TMP/allowed" || printf '%s\n' "$line" >> "$TMP/diff"
done < "$TMP/raw_diff"

n_diff=$(wc -l < "$TMP/diff")
n_allow=$(wc -l < "$TMP/allowed")
verdict=PASS
[ "$n_diff" = 0 ] || verdict=FAIL

# DRIFT_QUIET=1 prints the verdict and writes no artifact. check_docs.sh runs before every
# commit, and a gate that appends a file to evidence/ every time someone commits turns the
# evidence directory into a log. The evidenced run is the one you do for the record.
if [ "${DRIFT_QUIET:-0}" = "1" ]; then
  [ "${KEEP_REF:-0}" = "1" ] || ch --query "DROP DATABASE IF EXISTS $REF"
  if [ "$verdict" = PASS ]; then
    echo "ok: $TARGET matches sql/schema/ ($n_allow allowed generation differences)"
    exit 0
  fi
  echo "FAIL: $TARGET has $n_diff difference(s) from sql/schema/:" >&2
  sed 's/^/  /' "$TMP/diff" >&2
  exit 1
fi

{
  printf 'metric\tvalue\n'
  printf 'target_database\t%s\n'    "$TARGET"
  printf 'reference_database\t%s\t(empty, built from sql/schema/)\n' "$REF"
  printf 'drift_allow\t%s\n'        "${DRIFT_ALLOW:-<none>}"
  printf 'differences\t%s\t(required 0)\n' "$n_diff"
  printf 'allowed_differences\t%s\n'       "$n_allow"
  printf 'verdict\t%s\n' "$verdict"
  # The lines themselves, so the artifact says WHAT drifted and not merely how much.
  # `<` repo only, `>` server only.
  sed 's/^/difference\t/'        "$TMP/diff"
  sed 's/^/allowed_difference\t/' "$TMP/allowed"
} | evidence "schema_drift_${TARGET}" "live structure of ${TARGET} against sql/schema/, via an empty reference database" \
  | xargs cat

[ "${KEEP_REF:-0}" = "1" ] || ch --query "DROP DATABASE IF EXISTS $REF"

[ "$verdict" = PASS ] || { echo "SCHEMA DRIFT DETECTED in $TARGET" >&2; exit 1; }
