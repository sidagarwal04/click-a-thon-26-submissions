#!/usr/bin/env bash
# Give the derived tables a partition key, without changing a single derived value.
#
#   ./scripts/repartition_derived.sh --db phoenix_next --dry-run
#   ./scripts/repartition_derived.sh --db phoenix_next --yes
#   ./scripts/repartition_derived.sh --db phoenix --yes
#
# WHY. raw_events is PARTITION BY toYYYYMMDD(event_timestamp), so clearing a live slice from it is
# an instant metadata drop. Every DERIVED table was created with no partition key at all, so the
# same operation there has to be a lightweight DELETE, which is a mutation. The cost is not
# theoretical: foreground_intervals had accumulated 100 mutations from repeated resets, and
# lightweight DELETE has a far worse failure mode than slowness -- a delete followed by
# re-inserting rows that match its predicate leaves the new rows MASKED. That was measured in this
# repo: 108,521 rows physically present in system.parts and invisible to every SELECT.
#
# WHY DAILY AND NOT MONTHLY. Monthly looks tidier and is wrong here. The frozen corpus is July and
# the live slice is August, so a monthly key separates them today; but the unseen day also lands in
# August and would then share a partition with demo rows, making the mandatory pre-unseen-day
# cleanup impossible to do by partition. Daily keeps every day independently droppable. The
# partition count is ~13 corpus days plus live days, far inside the 100-1,000 band that
# schema-partition-low-cardinality asks for.
#
# WHY THE SMALL TABLES GET A KEY TOO, since concurrency_deltas is 61 KiB and the guidebook warns
# against partitioning small rollups. The justification here is LIFECYCLE, not scan pruning, which
# is exactly the purpose schema-partition-lifecycle names: these are precisely the tables
# reset_live.sh has to clear, and clearing them is the whole reason this script exists. Written
# down because a future reader would otherwise read it as cargo-culting the raw table's key.
#
# WHY COPY AND SWAP RATHER THAN DROP AND RE-DERIVE. A re-derive would change two things at once,
# the storage layout AND the derivation, and any difference afterwards would be unattributable.
# Copying holds the derivation constant so the gate below measures the layout change alone. The
# swap is EXCHANGE TABLES, which is atomic: materialized views target these tables by name and
# keep working across it.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
ASSUME_YES=0
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --db)      DB="$2"; shift 2;;
    --yes|-y)  ASSUME_YES=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done
export CH_DATABASE="$DB"
export EVIDENCE_STAMP_DB="$DB"
GUARD="${FROZEN_BEFORE:-2026-08-01}"

ch()  { ./scripts/ch.sh --select_sequential_consistency=1 "$@"; }
val() { ch --format TSVRaw --query "$1" 2>/dev/null | head -1; }

# table | partition expression | engine clause | INVARIANT expression
#
# THE INVARIANT IS PER ENGINE, and getting this wrong is the trap this repo already documents.
# A plain MergeTree can be verified with count(). A Collapsing or Summing table CANNOT: copying
# into a fresh table of the same engine lets it collapse pairs immediately, so physical rows
# legitimately fall while the asserted content is identical. Measured here on the first run:
# session_minute_runs copied 172,884 of 288,296 physical rows and the gate stopped the migration.
# The rows were not lost, they were collapsed. sum(sign) was unchanged.
#
# So the check is the aggregate the ENGINE maintains, which is the same rule
# docs/GROUND_STATE.md states as measurement rule 2: sum(sign) for Collapsing, sum(delta) for
# Summing, count() only for a plain MergeTree.
# Engine names are the PLAIN ones. ClickHouse Cloud maps MergeTree-family engines onto their
# Shared* equivalents automatically; naming SharedCollapsingMergeTree explicitly would need
# Cloud-only replication parameters and would not work anywhere else.
TABLES="
foreground_intervals|toYYYYMMDD(interval_start)|MergeTree|count()
session_minute_runs|toYYYYMMDD(run_start)|CollapsingMergeTree(sign)|sum(sign)
user_minute_runs|toYYYYMMDD(run_start)|CollapsingMergeTree(sign)|sum(sign)
concurrency_deltas|toYYYYMMDD(minute)|SummingMergeTree(delta)|concat(toString(sum(delta)),':',toString(uniqExact(minute)))
user_concurrency_deltas|toYYYYMMDD(minute)|SummingMergeTree(delta)|concat(toString(sum(delta)),':',toString(uniqExact(minute)))
concurrency_deltas_naive|toYYYYMMDD(minute)|SummingMergeTree(delta)|concat(toString(sum(delta)),':',toString(uniqExact(minute)))
concurrency_boundary_deltas|toYYYYMMDD(ts)|SummingMergeTree(delta)|concat(toString(sum(delta)),':',toString(uniqExact(ts)))
"

# ---------------------------------------------------------------------------------------------
# The gate. These five numbers describe the VALIDATED corpus and must be identical afterwards.
# sum(sign) on the Collapsing pair, never count(): count() reads physical rows and physical rows
# are a function of merge timing (docs/GROUND_STATE.md measurement rule 2).
# ---------------------------------------------------------------------------------------------
snapshot() {
  val "SELECT concat(
    toString((SELECT countIf(event_timestamp < '$GUARD') FROM raw_events)), '|',
    toString((SELECT countIf(interval_start  < '$GUARD') FROM foreground_intervals)), '|',
    toString((SELECT sumIf(sign, run_start   < '$GUARD') FROM session_minute_runs)), '|',
    toString((SELECT sumIf(sign, run_start   < '$GUARD') FROM user_minute_runs)), '|',
    toString((SELECT ifNull(max(c), 0) FROM (SELECT sum(d) OVER (ORDER BY minute) AS c FROM (
       SELECT minute, sum(delta) AS d FROM concurrency_deltas
       WHERE minute < '$GUARD' GROUP BY minute))))
  )"
}

BEFORE="$(snapshot)"
IFS='|' read -r b_raw b_fi b_smr b_umr b_peak <<<"$BEFORE"
echo "== $DB before: raw $b_raw  intervals $b_fi  session_runs $b_smr  user_runs $b_umr  peak $b_peak" >&2

[ "$b_raw" = "905558" ] || {
  echo "REFUSING: frozen raw_events is $b_raw, expected 905558. Fix that before restructuring." >&2
  exit 1; }

# ---------------------------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------------------------
PLAN=""
while IFS='|' read -r tbl part engine inv; do
  [ -z "$tbl" ] && continue
  exists="$(val "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = '$tbl'")"
  [ "${exists:-0}" = "1" ] || { echo "   skip $tbl (not in $DB)" >&2; continue; }
  cur="$(val "SELECT partition_key FROM system.tables WHERE database = currentDatabase() AND name = '$tbl'")"
  if [ -n "$cur" ]; then echo "   skip $tbl (already partitioned by $cur)" >&2; continue; fi
  echo "   will repartition $tbl BY $part" >&2
  PLAN="${PLAN}${tbl}|${part}|${engine}|${inv}
"
done <<<"$TABLES"

[ -n "$PLAN" ] || { echo "== nothing to do: every table already has a partition key" >&2; exit 0; }
[ "$DRY_RUN" = "1" ] && { echo "== --dry-run: nothing changed" >&2; exit 0; }

if [ "$ASSUME_YES" != "1" ]; then
  printf 'Repartition the above in %s? [y/N] ' "$DB" >&2
  read -r reply; case "$reply" in [yY]*) ;; *) echo "aborted" >&2; exit 1;; esac
fi

# ---------------------------------------------------------------------------------------------
# Copy, swap, drop. Per table, so a failure leaves every other table already done and this one
# untouched rather than half-migrated.
# ---------------------------------------------------------------------------------------------
DONE=""
while IFS='|' read -r tbl part engine inv; do
  [ -z "$tbl" ] && continue
  order="$(val "SELECT sorting_key FROM system.tables WHERE database = currentDatabase() AND name = '$tbl'")"
  [ -n "$order" ] || { echo "REFUSING: $tbl has no sorting key" >&2; exit 1; }

  echo "== $tbl: create shadow" >&2
  ch --query "DROP TABLE IF EXISTS ${tbl}__new" >/dev/null
  # `AS $tbl` copies the column definitions exactly, including codecs and defaults, so nothing is
  # retyped by hand and nothing can drift from the original.
  ch --query "CREATE TABLE ${tbl}__new AS $tbl ENGINE = $engine PARTITION BY $part ORDER BY ($order)" >/dev/null

  echo "== $tbl: copy" >&2
  ch --query "INSERT INTO ${tbl}__new SELECT * FROM $tbl" >/dev/null

  src="$(val "SELECT toString($inv) FROM $tbl")"
  dst="$(val "SELECT toString($inv) FROM ${tbl}__new")"
  if [ "$src" != "$dst" ]; then
    echo "REFUSING: $tbl invariant $inv is '$dst' after copy, was '$src'." >&2
    echo "  Shadow left in place as ${tbl}__new; the original is untouched." >&2
    exit 1
  fi

  echo "== $tbl: exchange ($inv = $src)" >&2
  ch --query "EXCHANGE TABLES $tbl AND ${tbl}__new" >/dev/null
  ch --query "DROP TABLE ${tbl}__new" >/dev/null
  DONE="${DONE}${tbl} "
done <<<"$PLAN"

# ---------------------------------------------------------------------------------------------
# Prove nothing moved
# ---------------------------------------------------------------------------------------------
AFTER="$(snapshot)"
IFS='|' read -r a_raw a_fi a_smr a_umr a_peak <<<"$AFTER"

verdict=PASS
[ "$BEFORE" = "$AFTER" ] || verdict=FAIL
unpart="$(val "SELECT count() FROM system.tables WHERE database = currentDatabase()
               AND name IN ('foreground_intervals','session_minute_runs','user_minute_runs',
                            'concurrency_deltas','user_concurrency_deltas')
               AND partition_key = ''")"
[ "${unpart:-1}" = "0" ] || verdict=FAIL

{
  printf 'metric\tvalue\n'
  printf 'database\t%s\n'                       "$DB"
  printf 'tables_repartitioned\t%s\n'           "$DONE"
  printf 'frozen.raw_events.before\t%s\n'       "$b_raw"
  printf 'frozen.raw_events.after\t%s\n'        "$a_raw"
  printf 'frozen.foreground_intervals.before\t%s\n' "$b_fi"
  printf 'frozen.foreground_intervals.after\t%s\n'  "$a_fi"
  printf 'frozen.session_runs.before\t%s\n'     "$b_smr"
  printf 'frozen.session_runs.after\t%s\n'      "$a_smr"
  printf 'frozen.user_runs.before\t%s\n'        "$b_umr"
  printf 'frozen.user_runs.after\t%s\n'         "$a_umr"
  printf 'frozen.peak_concurrency.before\t%s\n' "$b_peak"
  printf 'frozen.peak_concurrency.after\t%s\n'  "$a_peak"
  printf 'core_tables_still_unpartitioned\t%s\t(required 0)\n' "$unpart"
  printf 'verdict\t%s\n'                        "$verdict"
} | evidence "repartition_derived_$DB" "derived tables given a daily partition key, derivation held constant"

echo "== $DB repartition $verdict: peak $a_peak, unpartitioned core tables $unpart" >&2
[ "$verdict" = PASS ] || exit 1
