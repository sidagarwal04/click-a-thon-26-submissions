#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/ashiq/.local/bin:/usr/bin:/bin
# Load secrets from Windows-mounted .env without sourcing (CRLF-safe)
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
API_KEY=$(grep -E '^CLICKHOUSE_CLOUD_API_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
API_SECRET=$(grep -E '^CLICKHOUSE_CLOUD_API_SECRET=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
SID=$(grep -E '^CLICKHOUSE_SERVICE_ID=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
export CLICKHOUSE_CLOUD_API_KEY="$API_KEY"
export CLICKHOUSE_CLOUD_API_SECRET="$API_SECRET"

clickhousectl cloud auth login --api-key "$API_KEY" --api-secret "$API_SECRET" >/dev/null
clickhousectl cloud service query --id "$SID" --query "CREATE DATABASE IF NOT EXISTS otel" --format PrettyCompact
clickhousectl cloud service query --id "$SID" --query "SHOW DATABASES" --format PrettyCompact
