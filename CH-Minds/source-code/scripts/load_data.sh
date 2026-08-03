#!/bin/bash
# Bulk data load into ClickHouse, re-runnable for the Day-2 unseen slice.
#
#   ./scripts/load_data.sh [dir] [--allow-overlap] [--force]

set -euo pipefail
cd "$(dirname "$0")/.."

LOAD_DIR=""
ALLOW_OVERLAP=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --allow-overlap) ALLOW_OVERLAP=1 ;;
        --force)         FORCE=1 ;;
        *)               LOAD_DIR="$arg" ;;
    esac
done
LOAD_DIR="${LOAD_DIR:-data/inmobi}"

if [ ! -f "$LOAD_DIR/ad_events.parquet" ]; then
    echo "ERROR: $LOAD_DIR/ad_events.parquet not found." >&2
    echo "Place the InMobi data package (ad_events.parquet, apps.csv, advertisers.csv, geo_device.csv) in $LOAD_DIR first." >&2
    exit 1
fi

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

CH_USER="${CLICKHOUSE_USER:-ch_admin}"
CH_PASSWORD="${CLICKHOUSE_PASSWORD:-12345678}"

ch_insert() {
    local table="$1" format="$2" file="$3"
    docker compose exec -T clickhouse clickhouse-client \
        --user "$CH_USER" --password "$CH_PASSWORD" \
        --query "INSERT INTO $table FORMAT $format" < "$file"
}

ch_query() {
    docker compose exec -T clickhouse clickhouse-client \
        --user "$CH_USER" --password "$CH_PASSWORD" --query "$1"
}

EXISTING_ROWS="$(ch_query "SELECT count() FROM inmobi_rca.ad_events" 2>/dev/null || echo 0)"

# Staged, never inserted straight into ad_events - ad_events does not
# dedupe, so committing an already-loaded date range would double-count it.
echo "==> Staging ad_events for an overlap check before committing..."
ch_query "DROP TABLE IF EXISTS inmobi_rca.ad_events_staging"
ch_query "CREATE TABLE inmobi_rca.ad_events_staging AS inmobi_rca.ad_events"
ch_insert inmobi_rca.ad_events_staging Parquet "$LOAD_DIR/ad_events.parquet"

INCOMING_MIN="$(ch_query "SELECT toString(min(toDate(event_time))) FROM inmobi_rca.ad_events_staging")"
INCOMING_MAX="$(ch_query "SELECT toString(max(toDate(event_time))) FROM inmobi_rca.ad_events_staging")"
STAGED_ROWS="$(ch_query "SELECT count() FROM inmobi_rca.ad_events_staging")"
echo "    staged $STAGED_ROWS rows, covering $INCOMING_MIN .. $INCOMING_MAX"

if [ "${EXISTING_ROWS:-0}" -gt 0 ] && [ "$FORCE" -eq 0 ]; then
    OVERLAP_DAYS="$(ch_query "
        SELECT count() FROM (
            SELECT DISTINCT toDate(event_time) AS d FROM inmobi_rca.ad_events
            WHERE d BETWEEN toDate('$INCOMING_MIN') AND toDate('$INCOMING_MAX')
        )")"
    if [ "${OVERLAP_DAYS:-0}" -gt 0 ]; then
        if [ "$ALLOW_OVERLAP" -eq 1 ]; then
            echo "    --allow-overlap: dropping $OVERLAP_DAYS existing day partition(s) before committing."
            for part in $(ch_query "
                SELECT DISTINCT toString(toDate(event_time)) FROM inmobi_rca.ad_events
                WHERE toDate(event_time) BETWEEN toDate('$INCOMING_MIN') AND toDate('$INCOMING_MAX')"); do
                ch_query "ALTER TABLE inmobi_rca.ad_events DROP PARTITION '$part'"
                ch_query "ALTER TABLE inmobi_rca.hourly_segment_metrics DROP PARTITION '$part'"
            done
        else
            ch_query "DROP TABLE IF EXISTS inmobi_rca.ad_events_staging"
            echo "ERROR: $OVERLAP_DAYS day(s) in $INCOMING_MIN .. $INCOMING_MAX are already loaded." >&2
            echo "       Committing would DOUBLE-COUNT them - ad_events does not deduplicate." >&2
            echo "       Nothing was changed; the staging table has been dropped." >&2
            echo "       Re-run with --allow-overlap to drop and reload those day partitions," >&2
            echo "       or with --force to insert anyway (you almost certainly do not want this)." >&2
            exit 1
        fi
    else
        echo "    no overlap with the $EXISTING_ROWS rows already loaded - safe to commit."
    fi
fi

# Dimensions load before events commit (the MV joins against them at insert
# time); OPTIMIZE FINAL forces dedup immediately, not on the next merge.
echo "==> Loading dimension tables (apps, advertisers, geo_device)..."
ch_insert inmobi_rca.apps CSVWithNames "$LOAD_DIR/apps.csv"
ch_insert inmobi_rca.advertisers CSVWithNames "$LOAD_DIR/advertisers.csv"
ch_insert inmobi_rca.geo_device CSVWithNames "$LOAD_DIR/geo_device.csv"
ch_query "OPTIMIZE TABLE inmobi_rca.apps FINAL"
ch_query "OPTIMIZE TABLE inmobi_rca.advertisers FINAL"
ch_query "OPTIMIZE TABLE inmobi_rca.geo_device FINAL"

echo "==> Committing ad_events (this populates the hourly_segment_metrics rollup via the materialized view)..."
ch_query "INSERT INTO inmobi_rca.ad_events SELECT * FROM inmobi_rca.ad_events_staging"
ch_query "DROP TABLE inmobi_rca.ad_events_staging"

echo "==> Row counts:"
docker compose exec -T clickhouse clickhouse-client \
    --user "$CH_USER" --password "$CH_PASSWORD" \
    --query "
        SELECT 'ad_events' AS table, count() FROM inmobi_rca.ad_events
        UNION ALL SELECT 'apps', count() FROM inmobi_rca.apps
        UNION ALL SELECT 'advertisers', count() FROM inmobi_rca.advertisers
        UNION ALL SELECT 'geo_device', count() FROM inmobi_rca.geo_device
        UNION ALL SELECT 'hourly_segment_metrics', count() FROM inmobi_rca.hourly_segment_metrics
        FORMAT PrettyCompact
    "

echo "==> Done."
