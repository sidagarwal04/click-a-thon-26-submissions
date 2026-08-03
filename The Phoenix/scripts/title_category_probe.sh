#!/usr/bin/env bash
# Test 34 gate: title/category filters exist, answer from the serving layer, and the
# serving path reads ONLY concurrency_deltas + content. Asserted from system.query_log,
# not claimed: a run whose plan touches raw_events fails the artifact.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

category="${1:-bhdbj}"
from_ts="${2:-2026-07-26 00:00:00}"
to_ts="${3:-2026-07-27 00:00:00}"

marker="title_category_probe_$(date +%s)"

{
./scripts/ch.sh --format TSV \
  --param_title '' --param_category "$category" \
  --param_from_ts "$from_ts" --param_to_ts "$to_ts" --param_grain_s 86400 \
  --log_comment "$marker" --queries-file sql/queries/serving/title_category_peak_average.sql \
  | awk -v OFS='\t' -v c="$category" '{print "category_day", c, $0}'

# The serving query and this lookup can land on DIFFERENT replicas, and query_log is
# per-replica, so a single-node read misses the entry (the runbook's test 37 hit the same
# trap). clusterAllReplicas with skip_unavailable_shards, retried while the async flush
# catches up.
lookup="
SELECT 'serving_path_tables',
       arrayStringConcat(arraySort(arrayDistinct(tables)), ','),
       if(has(tables, currentDatabase() || '.raw_events'), 'FAIL', 'PASS')
FROM clusterAllReplicas(default, system.query_log)
WHERE type = 'QueryFinish' AND log_comment = '${marker}'
  AND event_time > now() - INTERVAL 10 MINUTE
ORDER BY event_time DESC LIMIT 1
SETTINGS skip_unavailable_shards = 1"

rows=""
for _ in 1 2 3 4 5 6; do
  ./scripts/ch.sh --query "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  rows="$(./scripts/ch.sh --format TSV --query "$lookup" 2>/dev/null || true)"
  [ -n "$rows" ] && break
  ./scripts/ch.sh --query "SELECT sleep(2) FORMAT Null" >/dev/null 2>&1 || true
done
if [ -n "$rows" ]; then
  printf '%s\n' "$rows"
else
  printf 'serving_path_tables\tquery_log entry not found on any reachable replica\tFAIL\n'
fi

./scripts/ch.sh --format TSV --query "
SELECT 'serving_path_read_rows', toString(read_rows), toString(read_bytes)
FROM clusterAllReplicas(default, system.query_log)
WHERE type = 'QueryFinish' AND log_comment = '${marker}'
  AND event_time > now() - INTERVAL 10 MINUTE
ORDER BY event_time DESC LIMIT 1
SETTINGS skip_unavailable_shards = 1" 2>/dev/null || true
} | evidence title_category_serving "title/category filter answers from concurrency_deltas + content only (category=$category)"
