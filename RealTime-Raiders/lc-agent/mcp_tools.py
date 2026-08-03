"""
mcp_tools.py
------------
Loads LangChain tools from the self-hosted mcp-clickhouse server over
streamable-http.

Why self-hosted rather than ClickHouse Cloud's remote MCP: the Cloud endpoint
authenticates via OAuth browser sign-in, which a headless agent cannot do.
The container here takes a static bearer token instead.

Env:
    MCP_CLICKHOUSE_URL   default http://mcp-clickhouse:8000/mcp
    MCP_AUTH_TOKEN       bearer token, must match the MCP server
"""

import os

from langchain_mcp_adapters.client import MultiServerMCPClient

_tools_cache: list | None = None


def _server_config() -> dict:
    url = os.getenv("MCP_CLICKHOUSE_URL", "http://mcp-clickhouse:8000/mcp")
    cfg: dict = {"url": url, "transport": "streamable_http"}
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if token:
        cfg["headers"] = {"Authorization": f"Bearer {token}"}
    return cfg


async def get_mcp_tools() -> list:
    """Fetch and cache the MCP server's tools as LangChain tools."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    client = MultiServerMCPClient({"clickhouse": _server_config()})
    _tools_cache = await client.get_tools()
    return _tools_cache
