#!/usr/bin/env bash
# Runs the official ClickHouse MCP server (github.com/ClickHouse/mcp-clickhouse),
# scoped read-only to the `atlys` database — this is the tool attached to
# analytics_agent and context_reviewer for real, live data queries.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a

export CLICKHOUSE_DATABASE=atlys
export CLICKHOUSE_ALLOW_WRITE_ACCESS=false
export CLICKHOUSE_MCP_SERVER_TRANSPORT=http
export CLICKHOUSE_MCP_BIND_HOST=0.0.0.0
export CLICKHOUSE_MCP_BIND_PORT=8101
# Local-network-only dev server (Docker bridge, not publicly exposed) — disabling
# auth here is a hackathon-scope tradeoff, not something to ship past that.
export CLICKHOUSE_MCP_AUTH_DISABLED=true

exec .venv/bin/mcp-clickhouse
