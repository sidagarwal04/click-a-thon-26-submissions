#!/usr/bin/env bash
# Apply every DDL file in sql/insights/schema/ to a database. Idempotent.
#
#   ./scripts/init_insights.sh                # $CH_DATABASE, then phoenix_next
#   ./scripts/init_insights.sh phoenix_next
#
# SEPARATE FROM init_db.sh ON PURPOSE. init_db.sh globs sql/schema/, so an insight table dropped
# into that directory would be created inside `phoenix` by any future init or by
# rebuild_swap.sh, which builds its shadow from those files. The concurrency engine and the
# insight layer have different lifecycles and different blast radii, so they get different
# directories and different appliers.
#
# Refuses to run against `phoenix`. That is the validated generation-1 database and this
# workstream does not write to it; the insight layer lives in phoenix_next. Override with
# ALLOW_PHOENIX=1 if that ever stops being true, which is a decision, not a flag.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
DB="${1:-${CH_DATABASE:-phoenix_next}}"
export CH_DATABASE="$DB"

if [ "$DB" = "phoenix" ] && [ "${ALLOW_PHOENIX:-0}" != "1" ]; then
  echo "REFUSING: phoenix is the validated generation-1 database." >&2
  echo "  The insight layer lives in phoenix_next. See docs/DECISIONS.md D9 and STATUS.md." >&2
  exit 1
fi

CH_DATABASE=default ./scripts/ch.sh --query "CREATE DATABASE IF NOT EXISTS $DB"

for f in sql/insights/schema/*.sql; do
  [ -e "$f" ] || { echo "no insight schema files yet"; exit 0; }
  echo "== $f"
  ./scripts/ch.sh --queries-file "$f"
done

./scripts/ch.sh --format PrettyCompact --query "
  SELECT name, engine FROM system.tables
  WHERE database = currentDatabase()
    AND name IN (SELECT name FROM system.tables WHERE database = currentDatabase())
    AND (name LIKE '%insight%' OR name LIKE '%late_event%' OR name LIKE '%audience%'
         OR name LIKE '%transitions%' OR name LIKE '%cohorts%' OR name LIKE '%spike%'
         OR name LIKE '%playback_health%')
  ORDER BY name"
