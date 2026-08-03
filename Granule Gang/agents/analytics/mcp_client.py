"""
Synchronous facade over the official ClickHouse MCP server (`mcp-clickhouse`,
https://github.com/ClickHouse/mcp-clickhouse).

AnalyticsAgent's existing call sites (run_query, sequential_funnel, ...) are all
plain synchronous methods, but the MCP Python SDK is async-only. Rather than make
AnalyticsAgent (and every caller in main.py) async, ClickHouseMCPClient spawns the
`mcp-clickhouse` subprocess once, runs its MCP ClientSession on a dedicated
background thread with its own event loop, and exposes plain blocking methods that
marshal calls onto that loop -- so `run_query()` can call `mcp_client.run_select_query(sql)`
exactly like it used to call `self.client.query(sql)`.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
import asyncio
import json
import threading

# Imported lazily/optionally: main.py and agent.py's __main__ block import this
# module unconditionally so the pipeline still runs (falling back to direct
# clickhouse_connect) on a checkout that hasn't run `pip install -r
# requirements.txt` yet to pick up the new `mcp`/`mcp-clickhouse` deps.
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_SDK_AVAILABLE = True
except ImportError:
    _MCP_SDK_AVAILABLE = False


class ClickHouseMCPClient:
    """One MCP session per instance -- construct it, use it, then close() it
    (or use as a context manager) to tear down the subprocess and background thread."""

    def __init__(self, ch_config, startup_timeout: float = 30.0):
        if not _MCP_SDK_AVAILABLE:
            raise RuntimeError("mcp package not installed -- run `pip install -r requirements.txt`.")

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None

        # Same CLICKHOUSE_* values agents/config.py:ClickHouseConfig already loads
        # from .env -- the MCP server reads them itself since it opens its own
        # ClickHouse connection rather than reusing an existing clickhouse_connect client.
        server_params = StdioServerParameters(
            command="mcp-clickhouse",
            args=[],
            env={
                "CLICKHOUSE_HOST": ch_config.host,
                "CLICKHOUSE_PORT": str(ch_config.port),
                "CLICKHOUSE_USER": ch_config.user,
                "CLICKHOUSE_PASSWORD": ch_config.password,
                "CLICKHOUSE_SECURE": "true" if ch_config.secure else "false",
                "CLICKHOUSE_DATABASE": ch_config.database,
            },
        )
        try:
            self._run(self._start(server_params), timeout=startup_timeout)
        except Exception:
            self._stop_loop()
            raise

    async def _start(self, server_params: StdioServerParameters) -> None:
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    def _run(self, coro, timeout: float = 60.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def _stop_loop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10.0)
        self._loop.close()

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        result = await self._session.call_tool(name, arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        if result.isError:
            raise RuntimeError(f"ClickHouse MCP tool '{name}' failed: {text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def run_select_query(self, query: str, timeout: float = 60.0) -> List[Dict[str, Any]]:
        """Run a read-only SQL query through the MCP server's `run_query` tool
        (read-only by default -- see mcp_clickhouse.mcp_server._validate_query_for_destructive_ops).
        That tool returns `{"columns": [...], "rows": [[...], ...]}`; reshape into
        a list of dicts -- the same shape AnalyticsAgent.run_query() already
        returns for the direct clickhouse_connect path."""
        result = self._run(self._call_tool("run_query", {"query": query}), timeout=timeout)
        columns = result.get("columns", []) if isinstance(result, dict) else []
        rows = result.get("rows", []) if isinstance(result, dict) else []
        return [dict(zip(columns, row)) for row in rows]

    def list_tables(self, database: str, timeout: float = 30.0) -> List[Dict[str, Any]]:
        result = self._run(self._call_tool("list_tables", {"database": database}), timeout=timeout)
        return result.get("tables", []) if isinstance(result, dict) else []

    def list_databases(self, timeout: float = 30.0) -> List[str]:
        result = self._run(self._call_tool("list_databases", {}), timeout=timeout)
        return result if isinstance(result, list) else []

    def close(self) -> None:
        if self._exit_stack is not None:
            try:
                self._run(self._exit_stack.aclose(), timeout=10.0)
            except Exception:
                pass
        self._stop_loop()

    def __enter__(self) -> "ClickHouseMCPClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    @classmethod
    def connect_or_none(cls, ch_config, startup_timeout: float = 30.0) -> Optional["ClickHouseMCPClient"]:
        """Best-effort constructor for callers (main.py's pipeline, this module's
        own __main__ block) that should keep running against clickhouse_connect
        directly -- same "degrade gracefully" pattern as OPENROUTER_API_KEY/
        ANTHROPIC_API_KEY elsewhere in this codebase -- rather than hard-fail when
        the `mcp-clickhouse` binary isn't installed or the server fails to start."""
        try:
            return cls(ch_config, startup_timeout=startup_timeout)
        except Exception as e:
            print(f"Warning: could not start ClickHouse MCP server ({e}) -- AnalyticsAgent will query ClickHouse directly instead.")
            return None
