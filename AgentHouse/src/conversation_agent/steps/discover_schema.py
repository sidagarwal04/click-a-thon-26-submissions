"""Step: discover_schema — NL + context catalog tools → SchemaContext."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from context_agent import get_context_catalog_tools
from conversation_agent import config
from conversation_agent.models import SchemaContext
from conversation_agent.shared import (
    agent_trace_metadata,
    build_model,
    setup_langfuse,
)

STEP_NAME = "discover_schema"

_FQN = config.activity_table_fqn()

INSTRUCTIONS = [
    "You select which ClickHouse tables, columns, and event names are relevant "
    "to the user's analytics question.",
    "ALWAYS call get_latest_context_items first (optionally filter kinds like "
    '"metric,funnel_step,entity,issue"). Use those items as the ONLY ground truth '
    "for business meaning, core funnel steps, metrics, joins, and known issues.",
    "If the question names a product feature (Express, Group, Forex, …), also call "
    "get_feature_meta(feature_id) for journey (order + ch_table) and columns maps "
    "(payload JSON keys).",
    "Do NOT call publish_context_version — Conversation is read-only.",
    f"Physical model is a Single Activity Schema: prefer table {_FQN} with "
    "envelope columns event_name, ch_table, timestamp (DateTime64), user_id, "
    "application_id, device_type, os, geoip_country_code, destination, and "
    "payload (JSON). Do not invent per-event physical tables for queries — "
    "Instrumentation MVs feed activity_events; use event_name filters.",
    "Do not invent tables, columns, or events that are not present in tool results. "
    "Catalog tools are the sole business ground truth; SAS envelope is the physical shape.",
    "If get_latest_context_items returns no context_version / empty items, or tools "
    "fail, return a SchemaContext with empty tables and event_names, and explain "
    "the failure clearly in notes (do not guess schema).",
    "Return a SchemaContext JSON: database (if known), tables (each with name, "
    "columns [{name, type?}], event_names), optional notes and rationale.",
    "Prefer the activity table only. Include envelope columns needed for filters/"
    "segments; list payload JSON keys only when tools document them for the question.",
    "When context_version is present in tool output, mention it in notes.",
]


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    return Agent(
        id=f"{config.AGENT_ID}-discover-schema",
        name="Discover Schema",
        model=build_model(),
        tools=[get_context_catalog_tools()],
        db=db,
        instructions=list(INSTRUCTIONS),
        output_schema=SchemaContext,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Select SAS tables/columns/events using context catalog tools",
        agent=build_agent(db=db),
    )
