"""Step: plan_visualization — SchemaContext → VizPlan (1–5 insights, no tools)."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from conversation_agent import config
from conversation_agent.models import VizPlan
from conversation_agent.shared import agent_trace_metadata, build_model, setup_langfuse

STEP_NAME = "plan_visualization"

INSTRUCTIONS = [
    "You plan one or more visualizations from a SchemaContext (tables, columns, "
    "event names) and the user's analytics question.",
    "Return a VizPlan JSON with: insights (list of VizSpec, length 1–5) and "
    "optional summary (how the set answers the question).",
    "Each VizSpec has: kind, optional title, metric_names, dimensions, "
    "event_names, time_window, rationale.",
    "Use multiple insights when the question needs complementary views "
    "(e.g. overall funnel + segment breakdown + trend). Prefer 1–3; "
    "never exceed 5. Use a single insight when one chart fully answers.",
    "Only use fields present in the schema / catalog. Do not invent columns "
    "or events.",
    "Physical fact table is the Single Activity Schema (activity_events): "
    "filter on event_name; segment on device_type / os / geoip_country_code / "
    "destination; payload metrics may need payload JSON keys when listed.",
    "Viz kind — pick the best fit among: timeseries, breakdown, comparison, "
    "table, funnel, metric, top_n.",
    "Prefer segment dimensions already in the envelope when relevant "
    "(device_type, geoip_country_code, destination, os).",
    "Give each insight a clear title so results stay distinguishable.",
]


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    return Agent(
        id=f"{config.AGENT_ID}-plan-visualization",
        name="Plan Visualization",
        model=build_model(),
        tools=[],
        db=db,
        instructions=list(INSTRUCTIONS),
        output_schema=VizPlan,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Choose 1–5 visualization insights from schema",
        agent=build_agent(db=db),
    )
