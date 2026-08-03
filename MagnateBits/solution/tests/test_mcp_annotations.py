"""MCP capability hints and the write-tool confirmation gate.

Why annotations: a host (LibreChat, Claude Desktop, an agent) can only distinguish a
safe read from a mutating call if the server says so in the protocol. Without hints it
either prompts for everything -- which trains the user to click through -- or prompts for
nothing. Seven of these tools only ever SELECT; `run_pipeline` proposes and executes DDL.

Why the confirm gate as well: `read_only_hint=False` lets a host warn, but nothing
*stops* the call, and a chat model will invoke a tool because its name looked relevant.
The refusal has to live server-side to actually bind.
"""

from __future__ import annotations

import inspect

import pytest

import atlys_mcp.server as server

READ_ONLY_TOOLS = [
    "list_features", "ask", "get_context", "list_contradictions",
    "explain_metric", "context_diff", "diagnose_segments",
]
WRITE_TOOLS = ["run_pipeline"]


def test_read_only_tools_are_annotated_read_only() -> None:
    assert server._READ_ONLY.read_only_hint is True
    assert server._READ_ONLY.idempotent_hint is True


def test_the_write_tool_is_annotated_as_writing_but_not_destructive() -> None:
    """Not destructive: the approval gate stands between a proposal and executed DDL,
    and loads are idempotent by truncate-then-insert. Not idempotent: a second call
    mints a new run_id and re-proposes a schema."""
    assert server._MUTATES.read_only_hint is False
    assert server._MUTATES.destructive_hint is False
    assert server._MUTATES.idempotent_hint is False


def test_every_tool_is_classified() -> None:
    """A new tool added without an annotation is the failure mode this catches:
    it would silently present as un-hinted to every client."""
    src = inspect.getsource(server)
    bare = src.count("@mcp.tool()")
    assert bare == 0, f"{bare} tool(s) registered without annotations"
    for name in READ_ONLY_TOOLS:
        assert f"@mcp.tool(annotations=_READ_ONLY)\ndef {name}(" in src, name
    for name in WRITE_TOOLS:
        assert f"@mcp.tool(annotations=_MUTATES)\ndef {name}(" in src, name


def test_run_pipeline_requires_confirmation() -> None:
    sig = inspect.signature(server.run_pipeline.fn if hasattr(server.run_pipeline, "fn")
                            else server.run_pipeline)
    assert "confirm" in sig.parameters, "run_pipeline must expose a confirm gate"
    assert sig.parameters["confirm"].default is False, "confirm must default to OFF"


def test_confirmless_call_reports_a_bad_path_rather_than_prompting() -> None:
    """Ordering matters: validating the path first means a typo'd spec_dir gets a real
    error instead of a confirmation prompt for a run that could never have happened."""
    fn = server.run_pipeline.fn if hasattr(server.run_pipeline, "fn") else server.run_pipeline
    out = fn(spec_dir="definitely_not_a_spec_dir", confirm=False)
    assert "not found" in out
    assert "confirmation_required" not in out


def test_confirmless_call_on_a_real_spec_does_not_run_anything() -> None:
    fn = server.run_pipeline.fn if hasattr(server.run_pipeline, "fn") else server.run_pipeline
    specs = sorted(p for p in server.SPECS_DIR.iterdir() if (p / "spec.md").exists()) \
        if server.SPECS_DIR.exists() else []
    if not specs:
        pytest.skip("no spec directories available")
    out = fn(spec_dir=specs[0].name, confirm=False)
    assert "confirmation_required" in out
    assert "run_id" not in out, "a confirm-less call must not have started a run"
