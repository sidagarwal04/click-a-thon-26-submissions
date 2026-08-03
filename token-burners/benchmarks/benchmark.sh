#!/usr/bin/env bash
# =============================================================================
# Benchmark Script for 008_queries.sql
# Runs all queries against ClickHouse and measures latency (cold + warm runs).
#
# Usage:
#   export CH_HOST=https://your-instance.clickhouse.cloud:8443
#   export CH_USER=default
#   export CH_PASS=your_password
#   export CH_DB=rohitdevtestingv8   # optional, defaults to rohitdevtestingv8
#   bash benchmark.sh [--runs N] [--warmup N] [--date YYYY-MM-DD]
#
# Options:
#   --runs N      Number of timed runs per query (default: 3)
#   --warmup N    Number of warmup runs before timing (default: 1)
#   --date DATE   Date to use in queries (default: 2026-07-31)
#   --output FILE Output results to a file (default: stdout + benchmark_results.md)
# =============================================================================

set -euo pipefail

# Load .env if present (check current dir, parent, grandparent)
if [[ -f ".env" ]]; then
    echo "Loading .env..."
    set -a
    source .env
    set +a
elif [[ -f "../.env" ]]; then
    echo "Loading ../.env..."
    set -a
    source ../.env
    set +a
elif [[ -f "../../.env" ]]; then
    echo "Loading ../../.env..."
    set -a
    source ../../.env
    set +a
fi

# Defaults
RUNS=3
WARMUP=1
QUERY_DATE="2026-07-31"
OUTPUT_FILE="benchmark_results.md"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --runs)   RUNS="$2"; shift 2 ;;
        --warmup) WARMUP="$2"; shift 2 ;;
        --date)   QUERY_DATE="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Connection defaults
CH_HOST="${CH_HOST:-https://localhost:8443}"
CH_USER="${CH_USER:-default}"
CH_PASS="${CH_PASS:-}"
CH_DB="${CH_DB:-rohitdevtestingv8}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║       ClickHouse Query Benchmark — Token Burners        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║ Host:    ${CH_HOST}"
echo "║ DB:      ${CH_DB}"
echo "║ Date:    ${QUERY_DATE}"
echo "║ Runs:    ${RUNS} (warmup: ${WARMUP})"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Helper: run a query and return elapsed time in ms
run_query() {
    local sql="$1"
    local start end elapsed
    start=$(python3 -c "import time; print(time.time())")
    curl -s --user "${CH_USER}:${CH_PASS}" \
        --data-binary "$sql" \
        "${CH_HOST}/?database=${CH_DB}&default_format=Null" \
        > /dev/null 2>&1
    end=$(python3 -c "import time; print(time.time())")
    elapsed=$(python3 -c "print(round((${end} - ${start}) * 1000, 2))")
    echo "$elapsed"
}

# All queries with labels
declare -a QUERY_NAMES
declare -a QUERIES

QUERY_NAMES+=("1a. Concurrency Curve (minute-level)")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("1b. Peak + Average Stats")
QUERIES+=("SELECT max(concurrent) AS peak_concurrent_viewers, argMax(minute, concurrent) AS peak_minute, round(avgIf(concurrent, concurrent > 0), 0) AS avg_concurrent, countIf(concurrent > 0) AS occupied_minutes FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) )")

QUERY_NAMES+=("2a. Filter: Platform (ANDROID_PHONE)")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND platform = 'ANDROID_PHONE' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2b. Filter: Country (india)")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND country = 'india' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2c. Filter: Video Type (live) via dict")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND dictGet('dict_content', 'video_type', content_id) = 'live' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2d. Filter: Show Name via dict")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND dictGet('dict_content', 'show_name', content_id) = 'bgfjb' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2e. Filter: Category via dict")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND dictGet('dict_content', 'category', content_id) = 'bffff' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2f. Filter: Video Resolution (1080p)")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND video_resolution = '1080p' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2g. Filter: Content Title via dict")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND dictGet('dict_content', 'title', content_id) = 'jipep dih' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("2h. Combined: Platform + Video Type")
QUERIES+=("SELECT minute, concurrent AS concurrent_viewers FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND platform = 'ANDROID_PHONE' AND dictGet('dict_content', 'video_type', content_id) = 'live' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 ORDER BY minute")

QUERY_NAMES+=("3a. Breakdown: Peak per Platform")
QUERIES+=("SELECT platform, max(concurrent) AS peak, argMax(minute, concurrent) AS peak_at FROM ( SELECT platform, minute, sum(d) OVER (PARTITION BY platform ORDER BY minute) AS concurrent FROM ( SELECT platform, minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY platform, minute ORDER BY platform, minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) GROUP BY platform ORDER BY peak DESC")

QUERY_NAMES+=("3b. Breakdown: Peak per Video Type")
QUERIES+=("SELECT dictGet('dict_content', 'video_type', content_id) AS video_type, max(concurrent) AS peak FROM ( SELECT content_id, minute, sum(d) OVER (PARTITION BY content_id ORDER BY minute) AS concurrent FROM ( SELECT content_id, minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY content_id, minute ) ) GROUP BY video_type ORDER BY peak DESC")

QUERY_NAMES+=("3c. Breakdown: Peak per Country")
QUERIES+=("SELECT country, max(concurrent) AS peak, argMax(minute, concurrent) AS peak_at FROM ( SELECT country, minute, sum(d) OVER (PARTITION BY country ORDER BY minute) AS concurrent FROM ( SELECT country, minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY country, minute ORDER BY country, minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) GROUP BY country ORDER BY peak DESC")

QUERY_NAMES+=("4. Active vs Open Sessions")
QUERIES+=("SELECT minute, active, open, round(active / greatest(open, 1) * 100, 1) AS pct_watching FROM ( SELECT minute, sum(da) OVER (ORDER BY minute) AS active, sum(do_val) OVER (ORDER BY minute) AS open FROM ( SELECT minute, sum(delta_sessions) AS da, sum(delta_open) AS do_val FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE active > 0 OR open > 0 ORDER BY minute")

QUERY_NAMES+=("5. Unique Users (time window)")
QUERIES+=("SELECT uniqMerge(active_users) AS unique_active_users, uniqMerge(open_users) AS unique_open_users, max(active_sessions) AS peak_active_sessions, max(open_sessions) AS peak_open_sessions FROM fact_concurrency_stats FINAL WHERE toDate(minute) = '${QUERY_DATE}' AND minute >= '${QUERY_DATE} 10:00:00' AND minute < '${QUERY_DATE} 12:00:00'")

QUERY_NAMES+=("6. Hourly Summary")
QUERIES+=("SELECT toStartOfHour(minute) AS hour, max(concurrent) AS peak, round(avg(concurrent), 0) AS avg_concurrent FROM ( SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent FROM ( SELECT minute, sum(delta_sessions) AS d FROM fact_concurrency_deltas FINAL WHERE toDate(minute) = '${QUERY_DATE}' GROUP BY minute ORDER BY minute WITH FILL FROM toDateTime('${QUERY_DATE} 00:00:00') TO toDateTime(toDate('${QUERY_DATE}') + INTERVAL 1 DAY) STEP INTERVAL 1 MINUTE ) ) WHERE concurrent > 0 GROUP BY hour ORDER BY hour")

# Collect results
declare -a RESULTS_MIN
declare -a RESULTS_MAX
declare -a RESULTS_AVG
declare -a RESULTS_P50

NUM_QUERIES=${#QUERY_NAMES[@]}

echo "Running ${NUM_QUERIES} queries × (${WARMUP} warmup + ${RUNS} timed) runs..."
echo ""

for i in $(seq 0 $((NUM_QUERIES - 1))); do
    name="${QUERY_NAMES[$i]}"
    sql="${QUERIES[$i]}"
    
    printf "  [%2d/%d] %-45s" "$((i+1))" "$NUM_QUERIES" "$name"
    
    # Warmup
    for w in $(seq 1 $WARMUP); do
        run_query "$sql" > /dev/null
    done
    
    # Timed runs
    latencies=()
    for r in $(seq 1 $RUNS); do
        ms=$(run_query "$sql")
        latencies+=("$ms")
    done
    
    # Calculate stats
    lat_csv=$(IFS=,; echo "${latencies[*]}")
    stats=$(python3 -c "
import statistics
lats = [${lat_csv}]
lats.sort()
mn = min(lats)
mx = max(lats)
avg = statistics.mean(lats)
med = statistics.median(lats)
print(f'{mn:.1f}|{mx:.1f}|{avg:.1f}|{med:.1f}')
")
    
    IFS='|' read -r mn mx avg med <<< "$stats"
    RESULTS_MIN+=("$mn")
    RESULTS_MAX+=("$mx")
    RESULTS_AVG+=("$avg")
    RESULTS_P50+=("$med")
    
    echo "  min=${mn}ms  avg=${avg}ms  p50=${med}ms  max=${mx}ms"
done

echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# Summary
avg_csv=$(IFS=,; echo "${RESULTS_AVG[*]}")
ALL_AVGS=$(python3 -c "
lats = [${avg_csv}]
print(f'Overall: min={min(lats):.1f}ms  avg={sum(lats)/len(lats):.1f}ms  max={max(lats):.1f}ms')
sub100 = sum(1 for l in lats if l < 100)
print(f'Queries under 100ms: {sub100}/{len(lats)} ({sub100/len(lats)*100:.0f}%)')
")
echo "$ALL_AVGS"

echo ""

# Write markdown report
{
    echo "# Benchmark Results — Token Burners"
    echo ""
    echo "**Date:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo "**Host:** ${CH_HOST}"
    echo "**Database:** ${CH_DB}"
    echo "**Query Date:** ${QUERY_DATE}"
    echo "**Config:** ${WARMUP} warmup + ${RUNS} timed runs per query"
    echo ""
    echo "## Results"
    echo ""
    echo "| # | Query | Min (ms) | Avg (ms) | P50 (ms) | Max (ms) |"
    echo "|---|-------|----------|----------|----------|----------|"
    for i in $(seq 0 $((NUM_QUERIES - 1))); do
        printf "| %d | %s | %s | %s | %s | %s |\n" \
            "$((i+1))" "${QUERY_NAMES[$i]}" "${RESULTS_MIN[$i]}" "${RESULTS_AVG[$i]}" "${RESULTS_P50[$i]}" "${RESULTS_MAX[$i]}"
    done
    echo ""
    echo "## Summary"
    echo ""
    echo "$ALL_AVGS"
    echo ""
    echo "---"
    echo "*Generated by benchmark.sh*"
} > "$OUTPUT_FILE"

echo "Results written to: ${OUTPUT_FILE}"
