"""MCP server exposing the context layer as real tools, so the Instrumentation/
Reviewer/Chronicler agents can pull exactly the sections they decide they need
mid-reasoning instead of being handed a pre-bundled dump by the orchestrator.

Run standalone (not spawned by LibreChat as a stdio subprocess — LibreChat's
container has no Python): `python mcp_servers/context_server.py`, then point
librechat.yaml's mcpServers at http://host.docker.internal:8100/mcp.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from mcp.server import FastMCP

from agent_meta.db import get_client

# NOTE: mcp-clickhouse's dependency pins downgraded the `mcp` package (2.0.0 ->
# 1.29.0) after it was installed, which renamed MCPServer -> FastMCP and moved
# host/port/stateless_http from run() kwargs to the constructor. Keep both MCP
# servers on this same version — don't let one upgrade silently break the other.
server = FastMCP(
    name="atlys_context", instructions="Query the Atlys business/data context layer.",
    host="0.0.0.0", port=8100, stateless_http=True,
)


@server.tool()
def list_context_sections() -> list[dict]:
    """Lists every section currently in the context layer with a one-line summary
    and confidence score, so you can decide which ones to fetch in full via
    lookup_context. Section key prefixes: overview:, entity:, table:, metric:,
    issue: (K1-K7), relationship:join_map, convention:, dataquality:."""
    client = get_client(database="agent_meta")
    rows = client.query(
        "SELECT section, confidence, content FROM current_context ORDER BY section"
    ).result_rows
    return [
        {"section": s, "confidence": conf, "summary": json.loads(c).get("summary", "")}
        for s, conf, c in rows
    ]


@server.tool()
def lookup_context(sections: list[str]) -> list[dict]:
    """Fetches the full current content for specific context sections by key
    (e.g. ["table:document_uploaded", "issue:K1"]). Use list_context_sections
    first if you're not sure of the exact keys."""
    if not sections:
        return []
    client = get_client(database="agent_meta")
    placeholders = ", ".join(f"%(s{i})s" for i in range(len(sections)))
    params = {f"s{i}": s for i, s in enumerate(sections)}
    rows = client.query(
        f"SELECT section, confidence, content FROM current_context WHERE section IN ({placeholders})",
        parameters=params,
    ).result_rows
    return [{"section": s, "confidence": conf, "content": json.loads(c)} for s, conf, c in rows]


if __name__ == "__main__":
    server.run(transport="streamable-http")
