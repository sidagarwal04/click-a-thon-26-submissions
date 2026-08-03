"""Smoke test for the tracing layer: emits one complete pipeline trace.

Run it before wiring real agents, and again right before the unseen-spec drop -
`make trace-check` is the fastest way to prove the trace path works end to end.
The shape it emits is the shape the real pipeline should produce: a root run,
one span per agent, decisions carrying reasoning, a pushed-down query, and a
confidence score.
"""

from __future__ import annotations

import logging

from .config import Settings
from .tracing import agent_step, init_tracing, is_enabled, pipeline_run, shutdown

log = logging.getLogger(__name__)

CONTEXT_VERSION = "demo-v0"


def run_trace_check(settings: Settings) -> int:
    live = init_tracing(settings)
    if not live:
        log.warning(
            "tracing is not live - the run below exercises the no-op path only. "
            "Start Langfuse with `make up-obs` and check LANGFUSE_HOST."
        )

    try:
        with pipeline_run("trace-check", spec_name="demo_feature", source="trace_check") as run:
            with agent_step(
                "context", "load_context", context_version=CONTEXT_VERSION
            ) as step:
                step.decision(
                    what=f"loaded context {CONTEXT_VERSION}",
                    why="analytics must reason from the newest version, not a cached snapshot",
                )
                step.output({"context_version": CONTEXT_VERSION, "entities": 0})

            with agent_step("instrumentation", "design_schema", input={"spec": "demo"}) as step:
                step.decision(
                    what="ORDER BY (agent_id, event_time)",
                    why=(
                        "agent_id appears in almost every predicate, so it belongs first; "
                        "event_time second gives range pruning without hurting the prefix"
                    ),
                    alternatives=["(event_time, agent_id)", "(session_id, event_time)"],
                    confidence=0.82,
                    evidence={"predicate_frequency": {"agent_id": 0.91, "event_time": 0.64}},
                )
                step.decision(
                    what="PARTITION BY toYYYYMM(event_time)",
                    why="monthly parts keep the count in the low hundreds at this volume",
                    confidence=0.9,
                )
                step.output({"tables": ["demo_events"], "materialized_views": 0})

            with agent_step(
                "analytics", "segment_analysis", context_version=CONTEXT_VERSION
            ) as step:
                step.sql(
                    "SELECT device, countIf(completed) / count() AS rate "
                    "FROM demo_events GROUP BY device",
                    purpose="completion rate by device, aggregated server-side",
                    rows=3,
                )
                step.decision(
                    what="mobile completion is 15% below desktop",
                    why="the gap opens on the same day the OTP flow shipped, per context",
                    confidence=0.71,
                    evidence={"desktop": 0.78, "mobile": 0.66},
                )
                step.score("confidence", 0.71, comment="single week of data; no A/B split")
                step.output({"insights": 1})

            run.output({"status": "ok", "insights": 1, "tables": 1})

            print(f"run_id:   {run.run_id}")
            print(f"trace_id: {run.trace_id or '(tracing off)'}")
            print(f"langfuse: {settings.langfuse_host}")
    finally:
        shutdown()

    if not is_enabled():
        print("\ntracing was NOT live - nothing reached Langfuse")
        return 1

    print("\ntrace emitted; search the run_id above in Langfuse to confirm")
    return 0
