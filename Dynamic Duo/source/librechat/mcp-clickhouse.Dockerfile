# mcp-clickhouse sidecar: the OFFICIAL ClickHouse MCP server (PyPI mcp-clickhouse),
# built ourselves so the transport is pinned to streamable HTTP regardless of what the
# Docker Hub image defaults to. Connects as the read-only librechat_ro user — every
# follow-up SELECT composed in chat runs SELECT-only.
FROM python:3.12-slim

# PyPI mcp-clickhouse is versioned 0.x (0.4.1 as of Aug 2026) — not 2.x
RUN pip install --no-cache-dir "mcp-clickhouse>=0.4,<1"

ENV CLICKHOUSE_MCP_SERVER_TRANSPORT=http \
    CLICKHOUSE_MCP_BIND_HOST=0.0.0.0 \
    CLICKHOUSE_MCP_BIND_PORT=8001

EXPOSE 8001
CMD ["mcp-clickhouse"]
