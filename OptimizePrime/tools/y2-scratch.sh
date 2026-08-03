#!/usr/bin/env bash
# tools/y2-scratch.sh — build one model variant into a LOCAL scratch database.
#
# Y2 (ADR 0031) needs the same pipeline built several times from the same input
# with one expression changed, so every claim in the ADR is a difference between
# two builds rather than a difference between two sessions. This is the harness
# that makes that cheap: it never touches Cloud, it refuses any database name
# that is not `y2_*`, and it re-copies ev_raw from `default` on every run so the
# input is provably identical across variants.
#
#   tools/y2-scratch.sh y2_base                 # build sql/ as committed
#   tools/y2-scratch.sh y2_fix  path/to/30.sql  # build with a substituted file
#
# Extra SQL files after the database name REPLACE the committed file of the same
# basename. Everything else comes from sql/.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:?usage: tools/y2-scratch.sh <y2_dbname> [override.sql ...]}"; shift || true
case "$DB" in
  y2_*) ;;
  *) echo "y2-scratch: refusing database '$DB' — Y2 scratch databases are named y2_*." >&2; exit 2 ;;
esac

# Overrides: basename -> path. Applied in place of sql/<basename>.
OVERRIDES=("$@")
# Which overrides were actually consumed. An override that matches nothing is a
# HARD ERROR at the end of the run, not a shrug: matching is by basename, so
# `--override /tmp/30.sql` does NOT match `sql/30_build_intervals.sql`, and the
# build silently applied the COMMITTED file while still calling itself a
# variant. That produced an ADR 0031 draft whose Q35 numbers described two
# identical builds (both 30,323 intervals). A variant harness that cannot tell
# you it built the baseline is worse than no harness.
#
# resolve() sets the global RESOLVED rather than echoing, because `$(resolve …)`
# would run it in a SUBSHELL and the USED bookkeeping below would be discarded
# — the assertion would then pass vacuously, which is the same silent failure it
# exists to catch.
USED=""
RESOLVED=""
resolve() {  # resolve <sql/NAME.sql> -> RESOLVED = the file to actually apply
  local want; want="$(basename "$1")"
  local o
  for o in ${OVERRIDES+"${OVERRIDES[@]}"}; do
    if [ "$(basename "$o")" = "$want" ]; then USED="$USED $o "; RESOLVED="$o"; return; fi
  done
  RESOLVED="$1"
}
assert_overrides_used() {
  local o
  for o in ${OVERRIDES+"${OVERRIDES[@]}"}; do
    case "$USED" in
      *" $o "*) ;;
      *) echo "y2-scratch: override '$o' matched NO applied file — its basename must equal a file in sql/ (e.g. 30_build_intervals.sql, not 30.sql). Refusing to call $DB a variant." >&2; exit 3 ;;
    esac
  done
}

q() { tools/ch "$1"; }             # against CH_DATABASE_LOCAL (default)
qdb() { CH_DATABASE_LOCAL="$DB" tools/ch "$1"; }
apply() { resolve "$1"; tools/apply-sql.sh --database "$DB" "$RESOLVED" >/dev/null; }

echo "== y2-scratch: $DB"
q "CREATE DATABASE IF NOT EXISTS $DB" >/dev/null

apply sql/00_schema.sql
apply sql/01_policy.sql
# ev_raw is re-copied every run: a variant that differs in its INPUT proves
# nothing about the expression that was changed.
qdb "TRUNCATE TABLE IF EXISTS ev_raw" >/dev/null
# Column list, never SELECT *: sql/00_schema.sql's ev_raw carries `ingested_at`
# and the loaded local table does not (the graded table gained it by ALTER — see
# ADR 0026), so a positional copy fails with a column-count mismatch.
EV_COLS="$(q "SELECT arrayStringConcat(groupArray(name), ', ') FROM system.columns WHERE database='default' AND table='ev_raw'")"
qdb "INSERT INTO ev_raw ($EV_COLS) SELECT $EV_COLS FROM default.ev_raw" >/dev/null

apply sql/10_intervals.sql
apply sql/15_normalise.sql
qdb "TRUNCATE TABLE IF EXISTS session_intervals" >/dev/null
apply sql/30_build_intervals.sql

# TRUNCATE before the user tier, for the reason ADR 0012 exists: cc_user_minute
# is keyed by (minute, dims), so a rebuild that changes ATTRIBUTION leaves the
# old bucket's row behind — it is never overwritten, only out-voted. Without
# this, re-running the harness compares a new model against a union of every
# model it has ever built, and the drift is always upward.
qdb "TRUNCATE TABLE IF EXISTS cc_user_minute" >/dev/null
apply sql/45_user_concurrency.sql

qdb "TRUNCATE TABLE IF EXISTS cc_minute_delta" >/dev/null
apply sql/40_deltas.sql

qdb "TRUNCATE TABLE IF EXISTS cc_hour_agg" >/dev/null
apply sql/50_hour_agg.sql

apply sql/20_views.sql

assert_overrides_used

printf '   intervals=%s  hours=%s\n' \
  "$(qdb "SELECT count() FROM session_intervals FINAL")" \
  "$(qdb "SELECT round(sum(dateDiff('second', interval_start, interval_end))/3600, 1) FROM session_intervals FINAL")"
