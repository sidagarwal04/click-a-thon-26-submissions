#!/bin/bash
# Creates the least-privilege read-only ClickHouse user, before 01-schema.sql
# grants it SELECT.

set -e

clickhouse-client -n <<-EOSQL
    -- ch_admin already exists (image entrypoint) - do not CREATE USER IF NOT
    -- EXISTS it here, that throws ACCESS_STORAGE_READONLY under set -e and
    -- silently skips every init file after this one.
    CREATE USER IF NOT EXISTS ${CLICKHOUSE_READONLY_USER:-ro}
        IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_READONLY_PASSWORD:-12345678}';

    REVOKE ALL ON system.* FROM ${CLICKHOUSE_READONLY_USER:-ro};
EOSQL

echo "ClickHouse users provisioned: ch_admin (created by the image entrypoint, already full-access), ${CLICKHOUSE_READONLY_USER:-ro} (data access granted by 01-schema.sql)."
