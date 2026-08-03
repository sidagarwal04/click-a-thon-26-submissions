"""Step: generate_query — VizSpec → QuerySpec via activity-schema skill."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from conversation_agent import config
from conversation_agent.models import QuerySpec
from conversation_agent.shared import (
    agent_trace_metadata,
    build_model,
    load_text_file,
    setup_langfuse,
)

STEP_NAME = "generate_query"

_FQN = config.activity_table_fqn()
_TABLE = config.CLICKHOUSE_ACTIVITY_TABLE or "activity_events"

BASE_INSTRUCTIONS = [
    "Your input is a VizSpec (Pydantic JSON from plan_visualization).",
    "Follow the ClickHouse Activity Schema skill below in full before writing SQL.",
    f"CRITICAL: Always query {_FQN}. Do not use FROM events, funnel_events, or "
    "UNION per-event tables. Filter / windowFunnel conditions use `event_name`; "
    "time column is `timestamp` (DateTime64(3)). Envelope segments: device_type, "
    "os, geoip_country_code, destination. Event-specific fields live in `payload` "
    "(JSON — use JSONExtract*).",
    f"For conversion funnels use windowFunnel() on {_FQN} with "
    "toDateTime(timestamp) as the time arg (DateTime64 is illegal for "
    "windowFunnel). Comment window unit in seconds; ordered event_name "
    "conditions; cumulative countIf.",
    "Emit exactly one SELECT (or WITH … SELECT) in QuerySpec.sql — no tools, do not execute.",
    "Prefer SQL that returns step / entities / conversion_from_start "
    "(plus segment_value when VizSpec asks for a segment cut).",
    f"Also set QuerySpec.funnel, window_seconds, step_names, filters, tables_used "
    f"(['{_TABLE}']), and caveats for the skill JSON contract.",
    "Do not invent event names or payload keys absent from VizSpec / skill / catalog.",
    "Companion metrics (latency, AOV, K-factor) may need JSONExtract on payload — "
    "note in caveats; prefer one primary query.",
]


def load_query_skill() -> str:
    return load_text_file(config.GENERATE_QUERY_SKILL_PATH, label="generate_query skill")


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    skill_body = load_query_skill()
    return Agent(
        id=f"{config.AGENT_ID}-generate-query",
        name="Generate Query",
        model=build_model(),
        tools=[],
        db=db,
        instructions=[
            *BASE_INSTRUCTIONS,
            "Query skill:\n\n" + skill_body,
        ],
        output_schema=QuerySpec,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Generate activity_events ClickHouse SQL from VizSpec",
        agent=build_agent(db=db),
    )
