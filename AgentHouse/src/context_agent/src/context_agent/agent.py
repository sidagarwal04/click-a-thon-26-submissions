"""Read-only Context Agent — explains living catalog via catalog tools."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from agno.agent import Agent

from context_agent.tools import get_context_read_tools
from conversation_agent.shared import (
    agent_trace_metadata,
    build_model,
    setup_langfuse,
)

AGENT_ID = "context-agent"
AGENT_NAME = "Context Agent"
LANGFUSE_SERVICE_NAME = "clickathon-context-agent"

INSTRUCTIONS = [
    "You are the Atlys Context Agent. You explain the living business context "
    "layer (entities, metrics, joins, core funnel steps, issues, contradictions) "
    "and Instrumentation feature meta when asked.",
    "ALWAYS call get_latest_context_items first with no kinds filter so you load "
    "the full current catalog. Cite context_version in your answer.",
    "If the user names a product feature (Express, Group, Status sharing, "
    "Abandoned checkout, Forex, unseen_data / coupon, …), also call "
    "get_feature_meta(feature_id) for journey order, ch_table, and columns.",
    "Do NOT invent entities, metrics, events, or formulas missing from tool results.",
    "You are READ-ONLY: there is no publish tool. Never claim you updated context.",
    "If tools return empty / missing context_version, say so clearly and suggest "
    "running seed_v0 / Instrumentation publish — do not guess.",
    "When useful, surface gaps or contradictions implied by the items "
    "(e.g. conflicting definitions, missing feature entities).",
    "Answer in clear Markdown for a product / analytics audience.",
]


def build_agent(*, db: Any = None) -> Agent:
    """Build the read-only Context Agent (catalog tools only)."""
    setup_langfuse(service_name=LANGFUSE_SERVICE_NAME)
    return Agent(
        id=AGENT_ID,
        name=AGENT_NAME,
        model=build_model(),
        tools=[get_context_read_tools()],
        db=db,
        instructions=list(INSTRUCTIONS),
        markdown=True,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step="context_agent"),
    )


async def run_context_agent(prompt: str) -> str:
    agent = build_agent()
    run = await agent.arun(prompt)
    content = run.content
    if content is None:
        return ""
    return content if isinstance(content, str) else str(content)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Context Agent (living catalog Q&A)",
    )
    parser.add_argument(
        "prompt",
        nargs="+",
        help="Question about context / feature meta",
    )
    args = parser.parse_args(argv)
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        parser.error("prompt is required")
    print(asyncio.run(run_context_agent(prompt)))


if __name__ == "__main__":
    main()
