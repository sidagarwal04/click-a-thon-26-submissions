"""Direct MCP client bridge to our own MCP servers (context_server.py on 8100,
data_tools_server.py on 8102) -- replaces LibreChat as the thing that discovers
tool schemas and executes tool calls. Both servers already run standalone on the
host (see mcp_servers/*.py); this just talks to them directly instead of via
LibreChat's proxy, which is the whole point of this module (LibreChat's Agents
API never returns real function_call arguments/output, confirmed via direct
testing -- calling OpenAI's Responses API directly does).

Tool name convention kept from agents/prompts.py's AGENTS dict for continuity:
`{tool}_mcp_{server}`, e.g. `list_tables_mcp_atlys_data`. The suffix tells us
which server to route to; we don't need a separate mapping table for that.
"""
from __future__ import annotations

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

_SERVER_URLS = {
    "atlys_context": "http://localhost:8100/mcp",
    "atlys_data": "http://localhost:8102/mcp",
}

_SUFFIX_TO_SERVER = {f"_mcp_{name}": name for name in _SERVER_URLS}

# Cached per-server tool schemas (name -> {description, inputSchema}), fetched
# once per process rather than per call -- these don't change mid-run.
_schema_cache: dict[str, dict[str, dict]] = {}


def _split_tool_name(full_name: str) -> tuple[str, str]:
    """`list_tables_mcp_atlys_data` -> ('list_tables', 'atlys_data')."""
    for suffix, server in _SUFFIX_TO_SERVER.items():
        if full_name.endswith(suffix):
            return full_name[: -len(suffix)], server
    raise ValueError(f"Unrecognized tool name (no known _mcp_<server> suffix): {full_name}")


async def _fetch_schema(server: str) -> dict[str, dict]:
    async with streamablehttp_client(_SERVER_URLS[server]) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return {
                t.name: {"description": t.description or "", "inputSchema": t.inputSchema}
                for t in tools.tools
            }


async def _call_tool(server: str, tool_name: str, arguments: dict) -> str:
    async with streamablehttp_client(_SERVER_URLS[server]) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            # MCP tool results are a list of content blocks. That assumption
            # of "always a single text block" was wrong for any tool whose
            # Python return type is a top-level list (list_context_sections,
            # lookup_context, grep_scratch, read_scratch): FastMCP emits ONE
            # content block PER LIST ITEM, not one block containing the whole
            # array -- confirmed directly (list_context_sections's 30 real
            # sections came back as 30 separate blocks). Naively
            # newline-joining those isn't valid JSON at all (no brackets, no
            # commas), which broke every frontend widget expecting
            # Array.isArray(output) on tools that return a list (e.g.
            # ContextIndexWidget/ContextLookupWidget silently rendered as
            # empty). Reassemble multi-block results into a real JSON array
            # when each block parses as JSON; a single block (the common
            # case -- every dict-returning tool) is returned as-is unchanged.
            parts = [getattr(c, "text", str(c)) for c in result.content]
            if len(parts) <= 1:
                return parts[0] if parts else ""
            try:
                return json.dumps([json.loads(p) for p in parts])
            except json.JSONDecodeError:
                return "\n".join(parts)


def openai_tool_defs(tool_names: list[str]) -> list[dict]:
    """Converts our `{tool}_mcp_{server}` names into OpenAI Responses API
    function-tool definitions, using each server's REAL schema (fetched live,
    not hand-maintained -- stays in sync with mcp_servers/*.py automatically)."""
    needed_servers = {_split_tool_name(n)[1] for n in tool_names}
    for server in needed_servers:
        if server not in _schema_cache:
            _schema_cache[server] = asyncio.run(_fetch_schema(server))

    defs = []
    for full_name in tool_names:
        short_name, server = _split_tool_name(full_name)
        schema = _schema_cache[server][short_name]
        defs.append({
            "type": "function",
            "name": full_name,  # keep the full name so call results route back correctly
            "description": schema["description"],
            "parameters": schema["inputSchema"],
        })
    return defs


def execute_tool(full_name: str, arguments_json: str) -> str:
    """Executes one tool call by its full `{tool}_mcp_{server}` name. Returns
    the tool's real output as a string (for the function_call_output item) --
    this is the actual payload LibreChat's proxy never gave us."""
    short_name, server = _split_tool_name(full_name)
    try:
        arguments = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Could not parse tool arguments as JSON: {e}"})
    try:
        return asyncio.run(_call_tool(server, short_name, arguments))
    except Exception as e:
        return json.dumps({"error": str(e)})
