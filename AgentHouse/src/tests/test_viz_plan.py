"""Unit tests for multi-insight VizPlan parsing in run_analytics step."""

from __future__ import annotations

from conversation_agent.models import VizPlan, VizSpec
from conversation_agent.steps.run_analytics import _parse_viz_plan


def test_parse_viz_plan_from_viz_spec() -> None:
    viz = VizSpec(kind="funnel", event_names=["a", "b"], title="Core funnel")
    plan = _parse_viz_plan(viz)
    assert isinstance(plan, VizPlan)
    assert len(plan.insights) == 1
    assert plan.insights[0].title == "Core funnel"


def test_parse_viz_plan_from_plan() -> None:
    plan_in = VizPlan(
        summary="two views",
        insights=[
            VizSpec(kind="funnel", event_names=["a", "b"]),
            VizSpec(kind="breakdown", dimensions=["device_type"]),
        ],
    )
    plan = _parse_viz_plan(plan_in)
    assert plan.summary == "two views"
    assert len(plan.insights) == 2


def test_parse_viz_plan_from_legacy_dict() -> None:
    plan = _parse_viz_plan({"kind": "table", "event_names": ["x"], "title": "T"})
    assert len(plan.insights) == 1
    assert plan.insights[0].kind == "table"


def test_parse_viz_plan_from_plan_dict() -> None:
    plan = _parse_viz_plan(
        {
            "summary": "s",
            "insights": [
                {"kind": "metric", "metric_names": ["users"], "title": "Users"},
            ],
        }
    )
    assert plan.summary == "s"
    assert plan.insights[0].kind == "metric"
