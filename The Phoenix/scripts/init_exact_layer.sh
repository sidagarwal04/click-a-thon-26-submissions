#!/usr/bin/env bash
# Create the exact-resolution serving layer and backfill it from foreground_intervals.
#
# Guarded the same way the derive is: the MV covers every insert into foreground_intervals
# from now on, so the backfill must run EXACTLY ONCE. Running it against a non-empty table
# would double every boundary delta, so a non-empty table refuses the backfill outright.
set -euo pipefail
cd "$(dirname "$0")/.."

./scripts/ch.sh --queries-file sql/schema/06_exact_concurrency.sql

existing=$(./scripts/ch.sh --query "SELECT count() FROM concurrency_boundary_deltas")
if [ "$existing" != "0" ]; then
  echo "refusing backfill: concurrency_boundary_deltas already holds $existing rows" >&2
  echo "a second backfill would double every delta; TRUNCATE it first if a rebuild is intended" >&2
  exit 1
fi

./scripts/ch.sh --query "
INSERT INTO concurrency_boundary_deltas
SELECT platform, country, video_type, content_id, app_version, b.1 AS ts, b.2 AS delta
FROM foreground_intervals
ARRAY JOIN [(interval_start, 1), (interval_end, -1)] AS b
WHERE interval_start < interval_end"

./scripts/ch.sh --query "
SELECT 'rows', count() FROM concurrency_boundary_deltas
UNION ALL
SELECT 'net_delta', sum(delta) FROM concurrency_boundary_deltas" --format TSV
