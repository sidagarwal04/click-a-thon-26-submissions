"""
supervisor.py
-------------
The routing agent. Grok sits on top; each specialist is exposed to it as a
LangChain tool, so "which analyst should answer this" becomes an ordinary
tool-calling decision rather than a hand-written classifier.

Three things fall out of that choice:

  - The supervisor can call SEVERAL specialists for one question and
    synthesise, which a classify-then-dispatch router cannot.
  - Langfuse renders the whole thing as a nested tree: supervisor -> specialist
    -> MCP tool -> the actual SQL. One trace shows the full chain of reasoning
    from question to query.
  - Adding a fourth specialist means adding an AGENT_4_* block. No routing code
    changes.

The supervisor has NO database tools of its own. It cannot query ClickHouse and
cannot invent a number without a specialist having gone and fetched one.
"""

import contextvars

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from config import load_agents, load_supervisor
from llm_factory import build_llm
from langfuse_trace import run_config
from agent import run_agent

_AGENTS = load_agents()
_SUPERVISOR = load_supervisor(_AGENTS)

# Carries the LibreChat conversation id into the delegate tools, so every
# specialist call lands in the same Langfuse session as the supervisor run.
_session_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)


class _DelegateInput(BaseModel):
    question: str = Field(
        description=(
            "The full question for this specialist, self-contained. They cannot "
            "see the conversation, so restate any range, filter or entity the "
            "user mentioned earlier."
        )
    )


def _make_delegate_tool(agent_id: str, description: str) -> StructuredTool:
    async def _call(question: str) -> str:
        return await run_agent(
            agent_id,
            [{"role": "user", "content": question}],
            session_id=_session_ctx.get(),
        )

    return StructuredTool.from_function(
        coroutine=_call,
        name=f"ask_{agent_id.replace('-', '_')}",
        description=description,
        args_schema=_DelegateInput,
    )


_DEFAULT_DESCRIPTIONS = {
    "liv-concurrency": (
        "Concurrency analyst. Peak and average concurrent sessions, the exact "
        "minute a peak occurred, filtered slices by platform, country, content "
        "type or title, and trends over a time range. Use for any question that "
        "wants a concurrency number."
    ),
    "liv-segment": (
        "Segment analyst. Compares concurrency ACROSS platforms, countries, "
        "content types or titles: who carries the load, share of viewing, and "
        "whether segments peak at the same time. Use for comparisons and "
        "breakdowns rather than single figures."
    ),
    "liv-capacity": (
        "Capacity planner. Turns peak and average into provisioning advice — "
        "what to size for, headroom, and whether a peak looks recurring. Use "
        "for infrastructure and planning questions."
    ),
}


def supervisor_id() -> str | None:
    return _SUPERVISOR.id if _SUPERVISOR else None


def delegate_ids() -> list[str]:
    return list(_SUPERVISOR.delegates) if _SUPERVISOR else []


def _delegate_roster() -> str:
    lines = []
    for aid in _SUPERVISOR.delegates:
        cfg = _AGENTS[aid]
        desc = cfg.description or _DEFAULT_DESCRIPTIONS.get(aid, "Analytics specialist.")
        lines.append(f"  - ask_{aid.replace('-', '_')}: {desc}")
    return "\n".join(lines)


def _resolve_system() -> tuple[str, str]:
    """Supervisor prompt: Langfuse if configured, else the inline base text."""
    base, tag = _SUPERVISOR.system, "inline"

    if _SUPERVISOR.prompt_name:
        try:
            from langfuse import get_client

            prompt = get_client().get_prompt(
                _SUPERVISOR.prompt_name, label=_SUPERVISOR.prompt_label
            )
            try:
                base = prompt.compile()
            except Exception:  # noqa: BLE001
                base = prompt.prompt
            tag = f"{_SUPERVISOR.prompt_name}:v{prompt.version}"
        except Exception as e:  # noqa: BLE001 — never let prompt fetch break routing
            print(f"[langfuse] supervisor prompt fetch failed: {e}; using inline")
            tag = "inline-fallback"

    roster = f"\n\nYour team:\n{_delegate_roster()}\n"
    return base + roster, tag


_graph_cache: dict[str, object] = {}


def _build():
    system_text, tag = _resolve_system()
    cached = _graph_cache.get(tag)
    if cached is not None:
        return cached

    llm = build_llm(_SUPERVISOR)
    tools = [
        _make_delegate_tool(
            aid,
            _AGENTS[aid].description or _DEFAULT_DESCRIPTIONS.get(aid, "Analytics specialist."),
        )
        for aid in _SUPERVISOR.delegates
    ]
    graph = create_react_agent(llm, tools=tools, prompt=system_text)
    _graph_cache[tag] = graph
    return graph


def _to_lc_messages(messages: list[dict]) -> list:
    out = []
    for m in messages:
        role, content = m.get("role"), m.get("content", "")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


async def run_supervisor(messages: list[dict], session_id: str | None = None) -> str:
    """Route the conversation through the specialists and synthesise a reply."""
    if _SUPERVISOR is None:
        raise RuntimeError("No supervisor configured (set SUPERVISOR_ID)")

    token = _session_ctx.set(session_id)
    try:
        graph = _build()
        config = run_config(_SUPERVISOR.id, session_id)
        result = await graph.ainvoke({"messages": _to_lc_messages(messages)}, config=config)
        final = result["messages"][-1]
        return final.content if hasattr(final, "content") else str(final)
    finally:
        _session_ctx.reset(token)
