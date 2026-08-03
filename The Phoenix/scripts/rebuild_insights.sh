#!/usr/bin/env bash
# Recreate the insight layer from sql/insights/schema/ and repopulate it. Idempotent.
#
#   ./scripts/rebuild_insights.sh                  # phoenix_next
#   CH_DATABASE=phoenix_next ./scripts/rebuild_insights.sh
#
# WHY THIS EXISTS SEPARATELY FROM init_insights.sh. Every DDL file is `CREATE TABLE IF NOT
# EXISTS`, which makes init_insights.sh safe to re-run and completely unable to apply a changed
# ORDER BY. ORDER BY is immutable: there is no ALTER for it, so a key change means drop and
# recreate, and doing that by hand at a terminal is how a step gets missed.
#
# This is the counterpart to rebuild_swap.sh, which does the same job for the concurrency engine.
# The difference is that the engine's tables are the product and get a shadow database and an
# EXCHANGE; the insight tables are entirely derived from raw_events and foreground_intervals and
# rebuild in seconds, so a straight drop is cheaper than a shadow and loses nothing.
#
# REFUSES to run against phoenix. That is generation 1, and this workstream does not write to it.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
export CH_DATABASE="$DB" EVIDENCE_STAMP_DB="$DB"

[ "$DB" = "phoenix" ] && { echo "REFUSING: phoenix is generation 1 and read-only to this work." >&2; exit 1; }

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

# Materialized views first: a view outlives its target table and would then fail on every insert
# into the source. Order within the rest does not matter, they have no dependencies on each other.
VIEWS=(late_event_audit_mv)
TABLES=(late_event_audit session_insight_facts audience_minute_snapshot
        content_entry_cohorts playback_health_minute)

echo "== 1. dropping the insight layer in $DB (derived, rebuilt below)" >&2
for v in "${VIEWS[@]}";  do ch --query "DROP VIEW IF EXISTS $v";   done
for t in "${TABLES[@]}"; do ch --query "DROP TABLE IF EXISTS $t"; done

echo "== 2. recreating from sql/insights/schema/" >&2
./scripts/init_insights.sh "$DB" >/dev/null

echo "== 3. repopulating" >&2
./scripts/refresh_insights.sh >&2

# The keys the server ended up with, read back rather than assumed. A DDL file that failed to
# apply leaves the previous table in place, and every downstream check would still pass against
# it while the repo claimed a key the server had never seen.
{
  printf 'table\tsorting_key\tprimary_key\trows\n'
  for t in "${TABLES[@]}"; do
    printf '%s\t%s\t%s\t%s\n' "$t" \
      "$(val "SELECT sorting_key FROM system.tables WHERE database = currentDatabase() AND name = '$t'")" \
      "$(val "SELECT primary_key FROM system.tables WHERE database = currentDatabase() AND name = '$t'")" \
      "$(val "SELECT count() FROM $t")"
  done
  printf '#\tlateness_class_type\t%s\n' \
    "$(val "SELECT type FROM system.columns WHERE database = currentDatabase() AND table = 'late_event_audit' AND name = 'lateness_class'")"
} | evidence "rebuild_insights_${DB}" "insight layer recreated from sql/insights/schema/, with the keys the server actually ended up with" \
  | xargs cat

echo "REBUILT. Next: validate_insights.sh, then bench_insights.sh." >&2
