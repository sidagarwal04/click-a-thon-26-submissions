"""ClickHouse Model Context Protocol (MCP) Server.

Exposes standard FastMCP tools for querying and inspecting ClickHouse:
- `execute_query`: Runs SELECT queries on ClickHouse (or chDB fallback) and returns structured rows.
- `list_tables`: Lists all tables available in the current database.
- `describe_table`: Returns schema definitions (column names and types) for a given table.
- `show_create_table`: Returns the CREATE TABLE DDL for a given table.
"""
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from atlys_agentic import ch_client, chdb_client, paths, tracing

load_dotenv(paths.ATLYS_AGENTIC_DIR / "config" / ".env")
load_dotenv(paths.REPO_ROOT / ".env")

mcp_server = FastMCP("clickhouse-mcp")


@mcp_server.tool(name="execute_query", description="Execute a read-only SELECT query against ClickHouse")
def execute_query(query: str) -> list[dict[str, Any]]:
    """Execute a read-only SELECT query against ClickHouse with automatic fallback to chDB."""
    query_clean = query.strip()
    if not re.match(r"^\s*SELECT\b", query_clean, re.IGNORECASE):
        raise ValueError("MCP Tool 'execute_query' is restricted to read-only SELECT statements.")

    with tracing.step("mcp::execute_query", input={"query": query_clean}):
        try:
            rows = ch_client.select(query_clean)
            return rows
        except Exception as exc:
            # Fallback to embedded chDB if table query can be resolved via local files
            try:
                res = chdb_client.run(query_clean)
                return res
            except Exception:
                raise RuntimeError(f"ClickHouse MCP execute_query failed: {exc}")


@mcp_server.tool(name="list_tables", description="List all tables in the ClickHouse database")
def list_tables() -> list[str]:
    """Return a list of all table names available in ClickHouse."""
    with tracing.step("mcp::list_tables", input={}):
        try:
            rows = ch_client.select("SHOW TABLES")
            tables = [r.get("name") if isinstance(r, dict) else r[0] for r in rows]
            return tables
        except Exception:
            try:
                reg_tables = chdb_client.run("SELECT DISTINCT \"table\" FROM schema_registry")
                return [r.get("table") for r in reg_tables if r.get("table")]
            except Exception:
                return []


@mcp_server.tool(name="describe_table", description="Get column names and types for a ClickHouse table")
def describe_table(table_name: str) -> list[dict[str, Any]]:
    """Return column metadata (name, type) for the specified table."""
    with tracing.step("mcp::describe_table", input={"table_name": table_name}):
        try:
            rows = ch_client.select(f"DESCRIBE TABLE {table_name}")
            return rows
        except Exception:
            try:
                rows = chdb_client.run(
                    f"SELECT ddl, columns_json FROM schema_registry WHERE \"table\" = '{table_name}' ORDER BY version DESC LIMIT 1"
                )
                if rows and rows[0].get("columns_json"):
                    cols = json.loads(rows[0]["columns_json"])
                    return [{"name": c, "type": "String"} for c in cols]
            except Exception:
                pass
            return []


@mcp_server.tool(name="show_create_table", description="Get the CREATE TABLE DDL statement for a ClickHouse table")
def show_create_table(table_name: str) -> str:
    """Return the CREATE TABLE DDL statement for a table."""
    with tracing.step("mcp::show_create_table", input={"table_name": table_name}):
        try:
            rows = ch_client.select(f"SHOW CREATE TABLE {table_name}")
            if rows:
                first = rows[0]
                return first.get("statement") or first.get("create_table_query") or str(first)
        except Exception:
            try:
                rows = chdb_client.run(
                    f"SELECT ddl FROM schema_registry WHERE \"table\" = '{table_name}' ORDER BY version DESC LIMIT 1"
                )
                if rows and rows[0].get("ddl"):
                    return rows[0]["ddl"]
            except Exception:
                pass
        return ""


if __name__ == "__main__":
    mcp_server.run()
