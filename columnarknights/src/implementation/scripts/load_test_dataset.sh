#!/usr/bin/env bash
# Loads the synthetic test dataset (generate_test_dataset.py) into its own
# ClickHouse database (clickathon_test by default) -- never touches whatever
# database is configured in .env for the real data. Reuses the real
# apps/advertisers/geo_device dimension tables as-is; only ad_events_raw is
# the synthetic stream.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_DIR="../data"
TEST_DB="${1:-clickathon_test}"

if [ ! -f .env ]; then
  echo "Missing .env (copy .env.example -> .env and fill in ClickHouse creds)" >&2
  exit 1
fi
set -a
source .env
set +a

if [ ! -f "$DATA_DIR/test_ad_events.parquet" ]; then
  echo "Missing $DATA_DIR/test_ad_events.parquet -- run scripts/generate_test_dataset.py first" >&2
  exit 1
fi

PORT="${CLICKHOUSE_NATIVE_PORT:-9440}"
SECURE_FLAG=(--secure)
if [ "${CLICKHOUSE_SECURE:-true}" != "true" ]; then
  SECURE_FLAG=()
  PORT="${CLICKHOUSE_NATIVE_PORT:-9000}"
fi
CH_BASE=(--host "${CLICKHOUSE_HOST}" --port "${PORT}" "${SECURE_FLAG[@]}" --user "${CLICKHOUSE_USER}" --password "${CLICKHOUSE_PASSWORD}")

echo "==> Creating database ${TEST_DB} if missing"
clickhouse-client "${CH_BASE[@]}" --query "CREATE DATABASE IF NOT EXISTS ${TEST_DB}"
CH=(clickhouse-client "${CH_BASE[@]}" --database "${TEST_DB}")

echo "==> Dropping existing tables in ${TEST_DB} (idempotent full reload)"
"${CH[@]}" --multiquery --query "
DROP TABLE IF EXISTS fact_events;
DROP TABLE IF EXISTS ad_events_raw;
DROP TABLE IF EXISTS apps;
DROP TABLE IF EXISTS advertisers;
DROP TABLE IF EXISTS geo_device;
DROP TABLE IF EXISTS investigations;
"

echo "==> Applying DDL"
"${CH[@]}" --multiquery < sql/ddl.sql

echo "==> Loading dimension tables (real apps/advertisers/geo_device, reused as-is)"
"${CH[@]}" --query "INSERT INTO apps FORMAT CSVWithNames" < "$DATA_DIR/apps.csv"
"${CH[@]}" --query "INSERT INTO advertisers FORMAT CSVWithNames" < "$DATA_DIR/advertisers.csv"
"${CH[@]}" --query "INSERT INTO geo_device FORMAT CSVWithNames" < "$DATA_DIR/geo_device.csv"

echo "==> Loading synthetic test event stream"
"${CH[@]}" --query "INSERT INTO ad_events_raw FORMAT Parquet" < "$DATA_DIR/test_ad_events.parquet"

echo "==> Building denormalized fact_events"
"${CH[@]}" --multiquery < sql/build_fact.sql

echo "==> Row counts in ${TEST_DB}"
"${CH[@]}" --query "
SELECT 'apps' AS table, count() FROM apps
UNION ALL SELECT 'advertisers', count() FROM advertisers
UNION ALL SELECT 'geo_device', count() FROM geo_device
UNION ALL SELECT 'ad_events_raw', count() FROM ad_events_raw
UNION ALL SELECT 'fact_events', count() FROM fact_events
FORMAT PrettyCompact"

echo ""
echo "Loaded into database: ${TEST_DB}"
echo "Run: python3 scripts/validate_test_dataset.py"
