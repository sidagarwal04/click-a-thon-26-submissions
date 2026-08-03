#!/usr/bin/env bash
# Reset the LIVE slice of a database back to the validated corpus, leaving the frozen slice
# byte-for-byte untouched.
#
#   ./scripts/reset_live.sh                          # phoenix, boundary 2026-08-01, asks first
#   ./scripts/reset_live.sh --yes                    # no prompt
#   ./scripts/reset_live.sh --db phoenix_next --from 2026-08-01 --yes
#   ./scripts/reset_live.sh --dry-run                # show what would go, touch nothing
#
# This is the pre-demo reset AND the post-demo cleanup: same script, same boundary. Re-running
# it is free, which is the whole point. After a live demo against phoenix the synthetic rows
# MUST be removed before FROZEN_BEFORE moves forward for the unseen day, or they stop being
# "live" and silently become part of the frozen corpus the benchmark answers come from.
#
# WHY DROP PARTITION AND NOT DELETE, for raw_events. The table is PARTITION BY
# toYYYYMMDD(event_timestamp), so every live row is in a partition no frozen row shares.
# Dropping a partition is a metadata operation: instant, no mutation, no merge pressure, and
# structurally incapable of touching a July row. A lightweight DELETE of 1.45M rows is a
# mutation that rewrites parts and competes with the demo for merge threads (ClickHouse rule
# insert-mutation-avoid-delete: prefer DROP PARTITION).
#
# WHY PARTITIONS ARE ENUMERATED AND NOT HARDCODED. A one-hour run that starts at 23:30 UTC
# writes into two partitions. A hardcoded DROP PARTITION '20260801' would leave the second one
# behind, and it would be found later as "frozen" data nobody put there. So the list comes from
# system.parts at run time and every partition at or after the boundary goes.
#
# WHY THE DERIVED TABLES USE THREE DIFFERENT TIME COLUMNS. They genuinely do, verified against
# system.columns. A copy-pasted event_timestamp predicate fails on all six; worse, a
# wrong-but-existing column would delete frozen rows silently. The map is explicit below.
#
# WHY A run_start PREDICATE CANNOT SPLIT A COLLAPSING PAIR. session_minute_runs is
# CollapsingMergeTree keyed (video_session_id, run_start, run_end); a +1 and its -1 retraction
# share all three. A predicate on run_start therefore takes both rows or neither, and cannot
# leave a dangling retraction behind. Asserted after the fact anyway, below.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix}"
FROM="${FROZEN_BEFORE:-2026-08-01}"
ASSUME_YES=0
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --db)      DB="$2"; shift 2;;
    --from)    FROM="$2"; shift 2;;
    --yes|-y)  ASSUME_YES=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done
export CH_DATABASE="$DB"
export EVIDENCE_STAMP_DB="$DB"

ch()  { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

# The frozen boundary this run must not cross. Deleting at or below it would destroy the
# validated corpus, which is the one outcome this script exists to make impossible.
GUARD="${FROZEN_BEFORE:-2026-08-01}"
if [ "$(val "SELECT toDate('$FROM') < toDate('$GUARD')")" = "1" ]; then
  echo "REFUSING: boundary $FROM is before the frozen boundary $GUARD." >&2
  echo "  Everything from $FROM onward would be deleted, and that range contains the" >&2
  echo "  validated corpus the benchmark answers come from." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# The frozen slice, measured BEFORE. Every one of these must be identical after.
#
# raw_events carries a hardcoded expectation because it is the source of truth and
# docs/GROUND_STATE.md pins it at 905,558. The DERIVED counts deliberately do not: they are
# captured at run time and compared to themselves. Measured 2026-08-01 20:50, they had already
# drifted from GROUND_STATE (foreground_intervals 598,752 vs 599,137 documented;
# session_minute_runs 17,585 vs 17,604; user_minute_runs 16,582 vs 16,600) because the D13
# end-rule decision re-derived them AFTER that document was captured at 13:45. The serving peak
# was unchanged at 2,828, and sign integrity was clean, so this is stale documentation and not
# damage. Hardcoding those numbers would make this script refuse to run forever, for a reason
# that has nothing to do with whether the reset is safe. Asserting before == after is the
# invariant that actually matters and it holds no matter what the absolute values are.
#
# sum(sign), never count(), on the Collapsing pair: count() reads physical rows and physical
# rows are a function of merge timing (GROUND_STATE measurement rule 2).
# ---------------------------------------------------------------------------
frozen_snapshot() {
  val "SELECT concat(
    toString((SELECT countIf(event_timestamp < '$GUARD') FROM raw_events)), '|',
    toString((SELECT countIf(interval_start  < '$GUARD') FROM foreground_intervals)), '|',
    toString((SELECT sumIf(sign, run_start   < '$GUARD') FROM session_minute_runs)), '|',
    toString((SELECT sumIf(sign, run_start   < '$GUARD') FROM user_minute_runs)), '|',
    toString((SELECT max(c) FROM (SELECT sum(d) OVER (ORDER BY minute) AS c FROM (
       SELECT minute, sum(delta) AS d FROM concurrency_deltas
       WHERE minute < '$GUARD' GROUP BY minute))))
  )"
}

BEFORE="$(frozen_snapshot)"
IFS='|' read -r b_raw b_fi b_smr b_umr b_peak <<<"$BEFORE"

echo "== $DB frozen slice before reset (boundary $GUARD)" >&2
printf '   raw_events %s  foreground_intervals %s  session_runs %s  user_runs %s  peak %s\n' \
  "$b_raw" "$b_fi" "$b_smr" "$b_umr" "$b_peak" >&2

if [ "$b_raw" != "905558" ]; then
  echo "REFUSING: frozen raw_events is $b_raw, expected 905558 (docs/GROUND_STATE.md)." >&2
  echo "  The validated corpus is already not what it should be. Fix that before deleting" >&2
  echo "  anything, or this reset gets blamed for damage that predates it." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# What would go
# ---------------------------------------------------------------------------
BOUNDARY_PART="$(val "SELECT formatDateTime(toDate('$FROM'), '%Y%m%d')")"
PARTS="$(ch --format TSVRaw --query "
  SELECT DISTINCT partition FROM system.parts
  WHERE database = currentDatabase() AND table = 'raw_events' AND active
    AND partition >= '$BOUNDARY_PART'
  ORDER BY partition")"
live_rows="$(val "SELECT count() FROM raw_events WHERE event_timestamp >= '$FROM'")"

if [ -z "$PARTS" ] && [ "${live_rows:-0}" = "0" ]; then
  echo "== nothing to reset: no partitions at or after $BOUNDARY_PART, no live rows" >&2
else
  echo "== would drop partitions: $(echo "$PARTS" | tr '\n' ' ')(${live_rows} live raw rows)" >&2
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "== --dry-run: nothing was changed" >&2
  exit 0
fi

if [ "$ASSUME_YES" != "1" ]; then
  printf 'Drop the above from %s? This cannot be undone. [y/N] ' "$DB" >&2
  read -r reply
  case "$reply" in [yY]*) ;; *) echo "aborted" >&2; exit 1;; esac
fi

# ---------------------------------------------------------------------------
# 1. raw_events: drop whole partitions. alter_sync=2 so the drop is visible on every replica
#    before we measure, otherwise the after-snapshot can read a replica that still has them.
# ---------------------------------------------------------------------------
for p in $PARTS; do
  echo "== DROP PARTITION $p" >&2
  ch --alter_sync=2 --query "ALTER TABLE raw_events DROP PARTITION '$p'"
done

# ---------------------------------------------------------------------------
# 2. Derived tables: DROP PARTITION, same as raw_events.
#
# These used to be lightweight DELETEs, one per table, each needing its own time column, because
# the derived tables were created with no partition key at all. scripts/repartition_derived.sh
# gave every one of them PARTITION BY toYYYYMMDD(<its own time column>), so the whole special case
# collapses into the loop below.
#
# That is worth more than tidiness. A DELETE is a mutation: foreground_intervals had accumulated
# 100 of them from repeated resets. Worse, a lightweight DELETE followed by re-inserting rows that
# match its predicate leaves the new rows MASKED, measured in this repo at 108,521 rows physically
# present in system.parts and invisible to every SELECT. A partition drop is metadata only and
# leaves nothing behind that can mask a later insert.
#
# The fallback is kept deliberately. If a table somehow has no partition key -- an older
# generation, a hand-created table, a half-finished migration -- it is reported and skipped rather
# than silently left full, so a partial migration cannot masquerade as a clean reset.
# ---------------------------------------------------------------------------
drop_live_partitions() {
  local tbl="$1"
  [ "$(val "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = '$tbl'")" = "1" ] || {
    echo "   skip $tbl (not in this database)" >&2; return; }
  local key
  key="$(val "SELECT partition_key FROM system.tables WHERE database = currentDatabase() AND name = '$tbl'")"
  # THE PARTITION ID FORMAT MUST MATCH THE BOUNDARY FORMAT, and a string comparison will not tell
  # you when it does not. BOUNDARY_PART is YYYYMMDD. A table partitioned toYYYYMM produces ids like
  # '202608', and '202608' >= '20260801' evaluates to FALSE in ClickHouse because the shorter
  # string sorts first. The loop would then find nothing, drop nothing, and report success.
  #
  # Refusing is the only safe answer. Dropping a monthly partition against a daily boundary would
  # be worse than skipping it: partition 202607 holds the entire validated July corpus, so a
  # comparison that accidentally matched would destroy the graded data this script exists to
  # protect.
  case "$key" in
    *toYYYYMMDD*) : ;;
    "")           : ;;
    *)
      echo "   WARNING: $tbl partitions by '$key', not toYYYYMMDD, and was NOT cleared." >&2
      echo "     Its partition ids cannot be compared against the ${BOUNDARY_PART} boundary." >&2
      UNPARTITIONED="${UNPARTITIONED}${tbl}(${key}) "
      return;;
  esac
  if [ -z "$key" ]; then
    echo "   WARNING: $tbl has no partition key and was NOT cleared." >&2
    echo "     Run ./scripts/repartition_derived.sh --db $DB --yes, then reset again." >&2
    UNPARTITIONED="${UNPARTITIONED}${tbl} "
    return
  fi
  local parts
  parts="$(ch --format TSVRaw --query "
    SELECT DISTINCT partition FROM system.parts
    WHERE database = currentDatabase() AND table = '$tbl' AND active
      AND partition >= '$BOUNDARY_PART' ORDER BY partition")"
  [ -n "$parts" ] || { echo "   $tbl: nothing at or after $BOUNDARY_PART" >&2; return; }
  for p in $parts; do
    echo "== DROP PARTITION $p FROM $tbl" >&2
    ch --alter_sync=2 --query "ALTER TABLE $tbl DROP PARTITION '$p'"
  done
}
UNPARTITIONED=""
for t in foreground_intervals session_minute_runs user_minute_runs \
         concurrency_deltas user_concurrency_deltas concurrency_deltas_naive \
         concurrency_boundary_deltas; do
  drop_live_partitions "$t"
done

# ---------------------------------------------------------------------------
# 3. Local state.
#
# SEED the watermark, do not delete it. With no watermark derive_tick.sh falls back to
# max(event_timestamp) - FIRST_WINDOW_S, and once the live partitions are gone that max is the
# JULY max (2026-07-26 11:30). The first tick would then re-derive 10:30-11:30 on 2026-07-26,
# which is the frozen slice's own peak hour, while frozen_gate.sh is trying to prove those rows
# are stable. The second tick is worse: its watermark would be in July and max_ts would be now,
# so the window spans days and the incremental derive retracts and re-asserts the whole corpus
# mid-demo. Seeding it at the boundary makes the first tick cover the demo and nothing else.
#
# .ingest_arrivals.* is genuinely stale alive-population state and is removed.
# ---------------------------------------------------------------------------
echo "$FROM 00:00:00" > ".derive_watermark.$DB"
rm -f ".ingest_arrivals.$DB"
echo "== watermark seeded at $FROM 00:00:00, stale ingest state cleared" >&2

# ---------------------------------------------------------------------------
# 4. Prove the frozen slice survived.
# ---------------------------------------------------------------------------
AFTER="$(frozen_snapshot)"
IFS='|' read -r a_raw a_fi a_smr a_umr a_peak <<<"$AFTER"

# A retraction left without its assertion, or an assertion counted twice. Nothing else checks
# this at reset time: derive_tick.sh checks it per tick, but the reset runs before any tick.
neg="$(val "SELECT countIf(s < 0) FROM (SELECT sum(sign) AS s FROM session_minute_runs
            WHERE run_start < '$GUARD' GROUP BY video_session_id, run_start, run_end)")"
dup="$(val "SELECT countIf(s > 1) FROM (SELECT sum(sign) AS s FROM session_minute_runs
            WHERE run_start < '$GUARD' GROUP BY video_session_id, run_start, run_end)")"
residue="$(val "SELECT count() FROM raw_events WHERE event_timestamp >= '$FROM'")"

verdict=PASS
[ "$BEFORE" = "$AFTER" ]   || verdict=FAIL
# A table that could not be cleared because it lacks a partition key is a FAIL, not a warning.
# Leaving it green would mean reporting "0 live rows remain" while a derived table still holds
# them, which is precisely the kind of half-truth this script exists to make impossible.
[ -z "$UNPARTITIONED" ]    || verdict=FAIL
[ "${neg:-1}" = "0" ]      || verdict=FAIL
[ "${dup:-1}" = "0" ]      || verdict=FAIL
[ "${residue:-1}" = "0" ]  || verdict=FAIL

{
  printf 'metric\tvalue\n'
  printf 'database\t%s\n'                       "$DB"
  printf 'boundary\t%s\n'                       "$FROM"
  printf 'frozen_before\t%s\n'                  "$GUARD"
  printf 'partitions_dropped\t%s\n'             "$(echo "$PARTS" | tr '\n' ' ')"
  printf 'live_raw_rows_removed\t%s\n'          "$live_rows"
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
  printf 'invariant.negative_run_groups\t%s\n'  "$neg"
  printf 'invariant.duplicate_run_groups\t%s\n' "$dup"
  printf 'live_rows_remaining\t%s\n'            "$residue"
  printf 'tables_without_partition_key\t%s\t(required empty)\n' "${UNPARTITIONED:-none}"
  printf 'verdict\t%s\n'                        "$verdict"
} | evidence "reset_live_$DB" "live slice reset to the validated corpus, frozen slice unchanged"

echo "== $DB reset $verdict: frozen peak $a_peak, $residue live rows remain" >&2
[ "$verdict" = PASS ] || exit 1
