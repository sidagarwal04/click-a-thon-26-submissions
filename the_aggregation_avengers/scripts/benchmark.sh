#!/usr/bin/env bash
# Benchmark the serving layer and capture the evidence the rubric asks for.
#
#   scripts/benchmark.sh [tag]
#
# For each query: wall-clock latency, rows read, bytes read, and the query_id
# needed to pull the full trace out of system.query_log afterwards. The rubric
# is explicit that judges look at WHAT A QUERY READS, not just how fast it
# returns -- so read_bytes is the headline number here, not duration.
#
# Every gold query is paired with the equivalent silver query so the serving
# layer earns its place with a measured delta rather than an assertion.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env.local; set +a
TAG="${1:-baseline}"
RUN="bench_${TAG}_$(date +%s)"

run() {  # run <name> <layer> <sql>
    local name=$1 layer=$2 sql=$3
    local qid="${RUN}_${name}_${layer}"
    local t0 t1
    t0=$(python3 -c 'import time;print(time.time())')
    curl -sS --fail-with-body --user "$CH_USER:$CH_PASS" \
        --data-binary "$sql" "$CH_HOST/?query_id=$qid" >/dev/null
    t1=$(python3 -c 'import time;print(time.time())')
    printf '%s\t%s\t%s\t%.0f\n' "$name" "$layer" "$qid" \
        "$(python3 -c "print(($t1-$t0)*1000)")"
}

# --- the benchmark set -----------------------------------------------------
# Shapes taken from the problem statement: peak and average at minute/hour/day
# grain, with dimension filters. Replace with the organisers' set when it lands.
RANGE="minute >= '2026-07-26 10:00:00' AND minute < '2026-07-26 12:00:00'"
SRANGE="event_minute >= '2026-07-26 10:00:00' AND event_minute < '2026-07-26 12:00:00'"
HB="is_heartbeat = 1 AND is_duplicate = 0"

declare -a NAMES=(series_2h peak_platform peak_platform_type hourly_rollup top_content peak_full_day)
declare -a GOLD=(
"SELECT minute, uniqExactMerge(sessions) FROM gold_ccu_minute WHERE $RANGE GROUP BY minute ORDER BY minute"
"SELECT max(c) FROM (SELECT minute, uniqExactMerge(sessions) c FROM gold_ccu_minute WHERE $RANGE AND platform='ANDROID_PHONE' GROUP BY minute)"
"SELECT max(c) FROM (SELECT minute, uniqExactMerge(sessions) c FROM gold_ccu_minute WHERE $RANGE AND platform='ANDROID_PHONE' AND video_type='vod' GROUP BY minute)"
"SELECT toStartOfHour(minute) h, max(c) FROM (SELECT minute, uniqExactMerge(sessions) c FROM gold_ccu_minute GROUP BY minute) GROUP BY h ORDER BY h"
"SELECT content_id, max(c) p FROM (SELECT content_id, minute, uniqExactMerge(sessions) c FROM gold_ccu_minute WHERE $RANGE GROUP BY content_id, minute) GROUP BY content_id ORDER BY p DESC LIMIT 10"
"SELECT max(c) FROM (SELECT minute, uniqExactMerge(sessions) c FROM gold_ccu_minute GROUP BY minute)"
)
declare -a SILVER=(
"SELECT event_minute, uniqExact(video_session_id) FROM silver_events WHERE $HB AND $SRANGE GROUP BY event_minute ORDER BY event_minute"
"SELECT max(c) FROM (SELECT event_minute, uniqExact(video_session_id) c FROM silver_events WHERE $HB AND $SRANGE AND platform='ANDROID_PHONE' GROUP BY event_minute)"
"SELECT max(c) FROM (SELECT event_minute, uniqExact(video_session_id) c FROM silver_events WHERE $HB AND $SRANGE AND platform='ANDROID_PHONE' AND video_type='vod' GROUP BY event_minute)"
"SELECT toStartOfHour(event_minute) h, max(c) FROM (SELECT event_minute, uniqExact(video_session_id) c FROM silver_events WHERE $HB GROUP BY event_minute) GROUP BY h ORDER BY h"
"SELECT content_id, max(c) p FROM (SELECT content_id, event_minute, uniqExact(video_session_id) c FROM silver_events WHERE $HB AND $SRANGE GROUP BY content_id, event_minute) GROUP BY content_id ORDER BY p DESC LIMIT 10"
"SELECT max(c) FROM (SELECT event_minute, uniqExact(video_session_id) c FROM silver_events WHERE $HB GROUP BY event_minute)"
)

echo "run: $RUN"
for i in "${!NAMES[@]}"; do
    run "${NAMES[$i]}" gold   "${GOLD[$i]}"   >/dev/null
    run "${NAMES[$i]}" silver "${SILVER[$i]}" >/dev/null
done

# query_log is flushed asynchronously; force it before reading.
curl -sS --user "$CH_USER:$CH_PASS" --data-binary 'SYSTEM FLUSH LOGS' "$CH_HOST" >/dev/null
sleep 8   # Cloud flushes query_log lazily; 2s caught only a partial set

curl -sS --user "$CH_USER:$CH_PASS" "$CH_HOST" --data-binary "
SELECT
    -- strip the run prefix, then peel the trailing _gold / _silver off.
    -- Splitting on '_' directly does not work: the run tag contains underscores.
    replaceOne(query_id, '${RUN}_', '')                 AS suffix,
    arrayStringConcat(arraySlice(splitByChar('_', suffix), 1,
        length(splitByChar('_', suffix)) - 1), '_')     AS query,
    splitByChar('_', suffix)[-1]                        AS layer,
    round(query_duration_ms)                            AS ms,
    formatReadableQuantity(read_rows)                   AS rows_read,
    formatReadableSize(read_bytes)                      AS bytes_read,
    read_bytes                                          AS raw_bytes
-- ClickHouse Cloud's system.query_log is PER-REPLICA, and a plain read lands
-- on whichever node the connection routed to -- so it returns a partial,
-- non-deterministic subset of the run. clusterAllReplicas unions every node.
FROM clusterAllReplicas(default, system.query_log)
WHERE query_id LIKE '${RUN}%' AND type = 'QueryFinish'
ORDER BY query, layer DESC
FORMAT PrettyCompactMonoBlock"
