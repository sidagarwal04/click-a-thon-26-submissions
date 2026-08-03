#!/bin/bash
# First-boot init for the compose ClickHouse (mounted at /docker-entrypoint-initdb.d).
# Runs as the loopback-only passwordless default user (see clickhouse-users.xml) and
# creates the two service accounts:
#   rca_rw       — writer: load.sh, detector seeds, rca-mcp (incidents/steps/diagnoses)
#   librechat_ro — read-only: the mcp-clickhouse sidecar (sql/07 counterpart)
set -e

clickhouse client -n <<-EOSQL
    CREATE DATABASE IF NOT EXISTS rca;

    CREATE USER IF NOT EXISTS rca_rw
        IDENTIFIED BY '${RCA_RW_PASSWORD:-rca_rw_dev}';
    GRANT ALL ON rca.* TO rca_rw;
    GRANT SYSTEM RELOAD DICTIONARY ON *.* TO rca_rw;
    -- ClickStack: the otel-collector writes otel_traces/otel_logs into default.*
    -- as rca_rw, and the HyperDX connection (also rca_rw) reads them + rca.*
    GRANT ALL ON default.* TO rca_rw;

    CREATE USER IF NOT EXISTS librechat_ro
        IDENTIFIED BY '${LIBRECHAT_RO_PASSWORD:-librechat_ro}'
        SETTINGS readonly = 1, max_execution_time = 60, max_result_rows = 100000;
    GRANT SELECT ON rca.* TO librechat_ro;
EOSQL
echo "clickhouse-init: rca database + rca_rw + librechat_ro ready"
