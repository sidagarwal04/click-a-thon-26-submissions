#!/bin/bash
# One-shot bootstrap + load for ClickHouse Cloud, run once against a fresh
# (empty) Cloud service. Uses the local clickhouse docker container purely as
# a network client (clickhouse-client --host/--secure) - Cloud itself is the
# actual server, nothing runs against local ClickHouse here.
#
# Deliberately a SIMPLE one-shot load, not a replay of the local two-phase
# history (known batch under original dims, then unseen slice under
# regenerated dims - see EDGE_CASES.md EC-9). Cloud gets dimension tables at
# their FINAL (regenerated) values once, then all 10.5M ad_events in one
# INSERT each. Consequence: known-batch (pre-2026-07-06) segment attribution
# on Cloud will NOT match the local demo captures earlier in this project -
# accepted trade-off, see PROGRESS.md. The unseen-incident findings (the
# actual submission artifact) are unaffected since they were always computed
# after the dimension reload.
#
# Usage:
#   CLICKHOUSE_CLOUD_HOST=xxxxx.clickhouse.cloud \
#   CLICKHOUSE_CLOUD_USER=default \
#   CLICKHOUSE_CLOUD_PASSWORD=... \
#   CLICKHOUSE_READONLY_PASSWORD=... \
#   ./scripts/deploy_clickhouse_cloud.sh

set -euo pipefail
cd "$(dirname "$0")/.."

: "${CLICKHOUSE_CLOUD_HOST:?set CLICKHOUSE_CLOUD_HOST (e.g. abcd1234.us-east-1.aws.clickhouse.cloud)}"
: "${CLICKHOUSE_CLOUD_USER:?set CLICKHOUSE_CLOUD_USER (usually 'default')}"
: "${CLICKHOUSE_CLOUD_PASSWORD:?set CLICKHOUSE_CLOUD_PASSWORD}"
: "${CLICKHOUSE_READONLY_PASSWORD:?set CLICKHOUSE_READONLY_PASSWORD (new password for the ro user this script creates)}"
# clickhouse-client speaks the native TCP protocol, not HTTP - Cloud's HTTPS
# interface (8443) doesn't understand that framing. 9440 is Cloud's secure
# native port. Don't reuse CLICKHOUSE_HTTP_URL's :8443 here.
CLICKHOUSE_CLOUD_PORT="${CLICKHOUSE_CLOUD_PORT:-9440}"
CLICKHOUSE_READONLY_USER="${CLICKHOUSE_READONLY_USER:-ro}"

ch() {
    docker compose exec -T clickhouse clickhouse-client \
        --host "$CLICKHOUSE_CLOUD_HOST" --port "$CLICKHOUSE_CLOUD_PORT" --secure \
        --user "$CLICKHOUSE_CLOUD_USER" --password "$CLICKHOUSE_CLOUD_PASSWORD" "$@"
}

echo "==> Creating the least-privilege ro user..."
ch --query "
CREATE USER IF NOT EXISTS $CLICKHOUSE_READONLY_USER IDENTIFIED WITH sha256_password BY '$CLICKHOUSE_READONLY_PASSWORD';
REVOKE ALL ON system.* FROM $CLICKHOUSE_READONLY_USER;
"

echo "==> Applying schema (configs/clickhouse/01-schema.sql)..."
ch --multiquery < configs/clickhouse/01-schema.sql

echo "==> Loading dimension tables at their FINAL (unseen-slice) values..."
ch --query "INSERT INTO inmobi_rca.apps FORMAT CSVWithNames"        < data/inmobi_unseen/apps.csv
ch --query "INSERT INTO inmobi_rca.advertisers FORMAT CSVWithNames" < data/inmobi_unseen/advertisers.csv
ch --query "INSERT INTO inmobi_rca.geo_device FORMAT CSVWithNames"  < data/inmobi_unseen/geo_device.csv
ch --query "OPTIMIZE TABLE inmobi_rca.apps FINAL"
ch --query "OPTIMIZE TABLE inmobi_rca.advertisers FINAL"
ch --query "OPTIMIZE TABLE inmobi_rca.geo_device FINAL"

echo "==> Loading ad_events (known batch, 9M rows - this is the slow step, be patient)..."
ch --query "INSERT INTO inmobi_rca.ad_events FORMAT Parquet" < data/inmobi/ad_events.parquet

echo "==> Loading ad_events (unseen incident slice, 1.5M rows)..."
ch --query "INSERT INTO inmobi_rca.ad_events FORMAT Parquet" < data/inmobi_unseen/ad_events.parquet

echo "==> Row counts on Cloud:"
ch --query "
    SELECT 'ad_events' AS table, count() FROM inmobi_rca.ad_events
    UNION ALL SELECT 'apps', count() FROM inmobi_rca.apps
    UNION ALL SELECT 'advertisers', count() FROM inmobi_rca.advertisers
    UNION ALL SELECT 'geo_device', count() FROM inmobi_rca.geo_device
    UNION ALL SELECT 'hourly_segment_metrics', count() FROM inmobi_rca.hourly_segment_metrics
    FORMAT PrettyCompact
"

echo "==> Done. Set these in the backend's deployed env (Railway):"
echo "    CLICKHOUSE_HTTP_URL=https://$CLICKHOUSE_CLOUD_HOST:$CLICKHOUSE_CLOUD_PORT"
echo "    CLICKHOUSE_ADMIN_USER=$CLICKHOUSE_CLOUD_USER"
echo "    CLICKHOUSE_ADMIN_PASSWORD=<the password you passed in>"
echo "    CLICKHOUSE_READONLY_USER=$CLICKHOUSE_READONLY_USER"
echo "    CLICKHOUSE_READONLY_PASSWORD=<the password you passed in>"
