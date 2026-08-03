#!/usr/bin/env bash
# Proves that ingested_at cannot be used to freeze the dataset.
#
#   ./scripts/prove_ingested_at.sh
#
# ingested_at was added to phoenix.raw_events by ALTER at 2026-08-01 12:34:06, after the
# 905,558 July rows were already loaded. ClickHouse does not rewrite existing parts on ADD
# COLUMN: for any part written before the ALTER, the column is absent on disk and the DEFAULT
# expression is evaluated when the column is read. The DEFAULT is now().
#
# So for every one of those rows, ingested_at IS the wall clock of the reading query. Three
# reads, three different values. A predicate `ingested_at <= '<watermark>'` is therefore
# false for all of them, and a "frozen" validation set silently measures nothing but the
# live August rows.
#
# Read-only. No DDL, no writes.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

ch() { CH_DATABASE=phoenix ./scripts/ch.sh "$@" 2>/dev/null; }
JULY="toYYYYMMDD(event_timestamp) < 20260801"

echo "== reading ingested_at on the July rows three times, four seconds apart"
READS=""
for i in 1 2 3; do
  r="$(ch --format TSVRaw --query "
    SELECT toString(now()), toString(min(ingested_at)), toString(max(ingested_at)),
           toString(uniqExact(ingested_at)), toString(count())
    FROM raw_events WHERE $JULY" | head -1)"
  echo "   read $i: $r"
  READS="${READS}read_${i}_query_time	$(echo "$r" | cut -f1)
read_${i}_july_min_ingested_at	$(echo "$r" | cut -f2)
read_${i}_july_max_ingested_at	$(echo "$r" | cut -f3)
read_${i}_july_distinct_ingested_at	$(echo "$r" | cut -f4)
read_${i}_july_rows	$(echo "$r" | cut -f5)
"
  [ "$i" = 3 ] || sleep 4
done

# The consequence, stated as a count rather than an argument.
WM="$(ch --format TSVRaw --query "SELECT toString(now())" | head -1)"
CONSEQ="$(ch --format TSVRaw --query "
  SELECT toString(countIf($JULY)),
         toString(countIf($JULY AND ingested_at <= '$WM')),
         toString(countIf(NOT $JULY)),
         toString(countIf(NOT $JULY AND ingested_at <= '$WM'))
  FROM raw_events" | head -1)"

{
  printf 'metric\tvalue\n'
  printf '%s' "$READS"
  printf 'frozen_predicate\tingested_at <= %s\n' "$WM"
  printf 'july_rows_total\t%s\n'                  "$(echo "$CONSEQ" | cut -f1)"
  printf 'july_rows_surviving_frozen_filter\t%s\n' "$(echo "$CONSEQ" | cut -f2)"
  printf 'august_rows_total\t%s\n'                "$(echo "$CONSEQ" | cut -f3)"
  printf 'august_rows_surviving_frozen_filter\t%s\n' "$(echo "$CONSEQ" | cut -f4)"
  printf 'verdict\tingested_at is NOT usable as a freeze key\n'
} | evidence ingested_at_nondeterminism \
    "ingested_at is re-evaluated at read time for pre-ALTER parts, so a watermark filter erases the validated dataset" \
  | xargs cat
