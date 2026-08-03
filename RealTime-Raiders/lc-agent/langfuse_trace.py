"""
langfuse_trace.py
-----------------
Optional Langfuse tracing.

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are set, every agent run — the
LLM calls and each MCP tool call, including the SQL the agent generated — is
traced via the LangChain CallbackHandler. If the keys are absent this is a
no-op and the agent runs normally, so it is safe to leave wired in.

That SQL capture is the point for this project: the trace shows what the
agent asked ClickHouse, which is the evidence a reviewer needs to trust the
number in the answer.
"""

import os

_enabled = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
_handler = None


def tracing_enabled() -> bool:
    return _enabled


def get_handler():
    """Shared Langfuse CallbackHandler, or None if not configured."""
    global _handler
    if not _enabled:
        return None
    if _handler is None:
        try:
            from langfuse.langchain import CallbackHandler
            _handler = CallbackHandler()
        except Exception as e:  # noqa: BLE001 — tracing must never break the agent
            print(f"[langfuse] tracing disabled — handler init failed: {e}")
            return None
    return _handler


def run_config(agent_id: str, session_id: str | None = None) -> dict:
    """
    LangChain `config` for graph.ainvoke(): Langfuse callback plus trace
    metadata so runs are grouped and filterable. Empty dict when tracing off.
    """
    handler = get_handler()
    if handler is None:
        return {}

    metadata: dict = {"langfuse_tags": ["lc-agent", agent_id, "concurrency"]}
    if session_id:
        metadata["langfuse_session_id"] = session_id

    return {"callbacks": [handler], "metadata": metadata, "run_name": agent_id}
