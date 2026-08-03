#!/usr/bin/env bash
# Loads data/*.csv + data/ad_events.parquet into ClickHouse (Cloud or local),
# applies sql/ddl.sql, then builds the denormalized fact_events table.
set -euo pipefail
cd "$(dirname "$0")/.."
# data/ lives at the repo root, one level above implementation/ (this script's
# own project root) — everything else this script touches (.env, sql/) is
# relative to implementation/ itself.
DATA_DIR="../data/unseen"

if [ ! -f .env ]; then
  echo "Missing .env (copy .env.example -> .env and fill it in)" >&2
  exit 1
fi
set -a
source .env
set +a

SECURE_FLAG=()
PORT="${CLICKHOUSE_NATIVE_PORT:-9000}"
if [ "${CLICKHOUSE_SECURE:-true}" = "true" ]; then
  SECURE_FLAG=(--secure)
  PORT="${CLICKHOUSE_NATIVE_PORT:-9440}"
fi

CH_ARGS=(--host "${CLICKHOUSE_HOST}" --port "${PORT}" "${SECURE_FLAG[@]}" \
  --user "${CLICKHOUSE_USER}" --password "${CLICKHOUSE_PASSWORD}")

echo "==> Creating database ${CLICKHOUSE_DATABASE} if missing"
clickhouse-client "${CH_ARGS[@]}" --query "CREATE DATABASE IF NOT EXISTS ${CLICKHOUSE_DATABASE}"

CH=(clickhouse-client "${CH_ARGS[@]}" --database "${CLICKHOUSE_DATABASE}")

# echo "==> Dropping existing tables (idempotent full reload)"
# "${CH[@]}" --multiquery --query "
# DROP TABLE IF EXISTS fact_events;
# DROP TABLE IF EXISTS ad_events_raw;
# DROP TABLE IF EXISTS apps;
# DROP TABLE IF EXISTS advertisers;
# DROP TABLE IF EXISTS geo_device;
# "

echo "==> Applying DDL"
"${CH[@]}" --multiquery < sql/ddl.sql

echo "==> Loading dimension tables"
"${CH[@]}" --query "INSERT INTO apps FORMAT CSVWithNames" < "$DATA_DIR/apps.csv"
"${CH[@]}" --query "INSERT INTO advertisers FORMAT CSVWithNames" < "$DATA_DIR/advertisers.csv"
"${CH[@]}" --query "INSERT INTO geo_device FORMAT CSVWithNames" < "$DATA_DIR/geo_device.csv"

echo "==> Loading raw fact table (ad_events.parquet, ~9M rows)"
"${CH[@]}" --query "INSERT INTO ad_events_raw FORMAT Parquet" < "$DATA_DIR/ad_events.parquet"

echo "==> Building denormalized fact_events"
"${CH[@]}" --multiquery < sql/build_fact.sql

echo "==> Row counts"
"${CH[@]}" --query "
SELECT 'apps' AS table, count() FROM apps
UNION ALL SELECT 'advertisers', count() FROM advertisers
UNION ALL SELECT 'geo_device', count() FROM geo_device
UNION ALL SELECT 'ad_events_raw', count() FROM ad_events_raw
UNION ALL SELECT 'fact_events', count() FROM fact_events
FORMAT PrettyCompact"
