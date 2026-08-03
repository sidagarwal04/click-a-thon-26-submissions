"""ClickHouse Model Context Protocol (MCP) Client Adapter.

Provides a unified programmatic interface for agents and analytical flows
to interact with ClickHouse using the Model Context Protocol (MCP).
"""
import logging
from typing import Any

from atlys_agentic import mcp_server

logger = logging.getLogger(__name__)


class ClickHouseMCPClient:
    """Unified MCP Client for ClickHouse operations."""

    def __init__(self):
        self.server = mcp_server.mcp_server

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a read-only query using the MCP execute_query tool."""
        return mcp_server.execute_query(query)

    def list_tables(self) -> list[str]:
        """List all tables using the MCP list_tables tool."""
        return mcp_server.list_tables()

    def describe_table(self, table_name: str) -> list[dict[str, Any]]:
        """Describe a table schema using the MCP describe_table tool."""
        return mcp_server.describe_table(table_name)

    def show_create_table(self, table_name: str) -> str:
        """Get table CREATE statement using the MCP show_create_table tool."""
        return mcp_server.show_create_table(table_name)


# Global singleton client instance
_default_client = None


def get_mcp_client() -> ClickHouseMCPClient:
    """Return singleton ClickHouse MCP client."""
    global _default_client
    if _default_client is None:
        _default_client = ClickHouseMCPClient()
    return _default_client


def execute_query(query: str) -> list[dict[str, Any]]:
    """Convenience helper to execute a query via ClickHouse MCP."""
    return get_mcp_client().execute_query(query)


def list_tables() -> list[str]:
    """Convenience helper to list tables via ClickHouse MCP."""
    return get_mcp_client().list_tables()
