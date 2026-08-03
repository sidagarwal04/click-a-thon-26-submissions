#!/bin/bash
# Users and quotas. MUST be .sh, not .sql — the entrypoint runs .sql through
# clickhouse-client verbatim with NO shell, so '${AGENT_PASSWORD}' in a .sql file
# becomes the LITERAL password. Verified. See docs/VERIFIED.md.
set -euo pipefail
: "${AGENT_PASSWORD:?AGENT_PASSWORD not set - refusing to create a passwordless user}"

clickhouse-client -n <<SQL
-- The agent / MCP identity. readonly = 2, NOT 1: readonly=1 blocks the client from
-- setting max_execution_time (Code: 164), and every MCP server sets a per-query timeout.
-- readonly=2 is still safe: writes and escalation are blocked by GRANTS, not by this level.
CREATE USER IF NOT EXISTS agent_ro IDENTIFIED BY '${AGENT_PASSWORD}'
  SETTINGS readonly = 2,
           max_execution_time = 10   MAX 30,
           max_result_rows    = 2000 MAX 10000,
           max_memory_usage   = 4000000000;
GRANT SELECT ON default.* TO agent_ro;
CREATE QUOTA IF NOT EXISTS agent_q KEYED BY user_name
  FOR INTERVAL 1 MINUTE MAX queries 240, read_rows 5000000000 TO agent_ro;

-- The browser identity for the no-backend API (chcfg/handlers.xml).
-- readonly = 1 is correct here: it only ever passes typed parameters, never settings.
CREATE USER IF NOT EXISTS web_ro IDENTIFIED WITH no_password
  SETTINGS readonly = 1, max_execution_time = 10, max_rows_to_read = 2000000000;
GRANT SELECT ON default.* TO web_ro;
CREATE QUOTA IF NOT EXISTS web_q KEYED BY user_name
  FOR INTERVAL 1 MINUTE MAX queries 120, read_rows 5000000000 TO web_ro;
SQL
echo "05_users.sh: agent_ro (readonly=2, capped) and web_ro (readonly=1) created"
