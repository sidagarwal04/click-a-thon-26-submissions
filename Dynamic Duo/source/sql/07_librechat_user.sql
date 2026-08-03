-- Read-only ClickHouse user for the LibreChat surface: the official mcp-clickhouse
-- sidecar connects as librechat_ro, so every follow-up SELECT composed in chat runs
-- with SELECT-only grants — the hard control; readonly=1 is belt-and-braces defaults.
--
-- Local compose stack: applied automatically on first boot by
-- librechat/clickhouse-init.sh with LIBRECHAT_RO_PASSWORD from .env.
-- ClickHouse Cloud (the end-state env swap): run this file manually, replacing the
-- default password:
--   clickhouse client --host ... --secure --password ... --queries-file sql/07_librechat_user.sql

CREATE USER IF NOT EXISTS librechat_ro IDENTIFIED BY 'librechat_ro'
    SETTINGS readonly = 1, max_execution_time = 60, max_result_rows = 100000;

GRANT SELECT ON rca.* TO librechat_ro;
