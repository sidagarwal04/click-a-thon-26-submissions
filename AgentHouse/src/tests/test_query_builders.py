"""Unit tests for deterministic SQL builders (no ClickHouse required)."""

from __future__ import annotations

from conversation_agent.clickhouse_client import validate_select_sql
from conversation_agent.query_builders import AnalyticsPlan, build_sql, plan_from_viz_spec
from conversation_agent.models import VizSpec


def test_funnel_sql_parses():
    plan = AnalyticsPlan(
        kind="funnel",
        event_names=["application_started", "purchase_completed"],
        dimensions=["device_type"],
        time_window="last_30_days",
    )
    built = build_sql(plan)
    validate_select_sql(built.sql)
    assert "windowFunnel" in built.sql
    assert "application_started" in built.sql
    assert "event_name =" in built.sql
    assert "activity_events" in built.sql
    assert "funnel_events" not in built.sql


def test_breakdown_and_timeseries_parse():
    b = build_sql(
        AnalyticsPlan(
            kind="breakdown",
            event_names=["purchase_completed"],
            dimensions=["destination"],
            limit=10,
        )
    )
    validate_select_sql(b.sql)
    assert "event_name" in b.sql
    t = build_sql(
        AnalyticsPlan(kind="timeseries", event_names=["application_started"])
    )
    validate_select_sql(t.sql)
    assert "event_name" in t.sql


def test_viz_spec_maps_to_funnel():
    viz = VizSpec(
        kind="funnel",
        event_names=[],
        dimensions=["device_type"],
        time_window="last_7_days",
    )
    plan = plan_from_viz_spec(viz)
    assert plan.kind == "funnel"
    assert len(plan.event_names) >= 2
    assert "activity_events" in plan.table
    validate_select_sql(build_sql(plan).sql)
