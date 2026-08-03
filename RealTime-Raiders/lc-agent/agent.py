"""
agent.py
--------
One tool-using ReAct agent per AgentConfig, built with LangGraph's
create_react_agent. Tools come from the self-hosted mcp-clickhouse server —
the agent defines no DB tool of its own.

System prompts resolve through langfuse_prompts. The graph is cached by
(agent_id, prompt_version), so publishing a new production prompt in Langfuse
rebuilds the agent within the SDK's cache TTL, with no redeploy.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from config import AgentConfig, load_agents
from llm_factory import build_llm
from mcp_tools import get_mcp_tools
from langfuse_prompts import resolve_system_prompt
from langfuse_trace import run_config

_AGENTS = load_agents()
_graph_cache: dict[tuple[str, str], object] = {}


def list_agent_ids() -> list[str]:
    return list(_AGENTS.keys())


def get_agent_config(agent_id: str) -> AgentConfig | None:
    return _AGENTS.get(agent_id)


async def _build(agent_id: str):
    cfg = _AGENTS[agent_id]
    system_text, version_tag = resolve_system_prompt(cfg)

    key = (agent_id, version_tag)
    cached = _graph_cache.get(key)
    if cached is not None:
        return cached

    llm = build_llm(cfg)
    tools = await get_mcp_tools()
    graph = create_react_agent(llm, tools=tools, prompt=system_text)
    _graph_cache[key] = graph
    return graph


def _to_lc_messages(messages: list[dict]) -> list:
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


async def run_agent(
    agent_id: str,
    messages: list[dict],
    session_id: str | None = None,
) -> str:
    """Run the named agent over an OpenAI-style message list; return final text."""
    if agent_id not in _AGENTS:
        agent_id = list_agent_ids()[0]  # LibreChat may send a display label

    graph = await _build(agent_id)
    config = run_config(agent_id, session_id)
    result = await graph.ainvoke({"messages": _to_lc_messages(messages)}, config=config)
    final = result["messages"][-1]
    return final.content if hasattr(final, "content") else str(final)
