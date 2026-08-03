#!/usr/bin/env python3
"""Creates a "RCA Pipeline Latency" dashboard in Langfuse from real span data.

Every investigate/scan run already mirrors its Tracer spans into Langfuse
(see rca/tracing.py) whenever LANGFUSE_PUBLIC_KEY/SECRET_KEY are set. This
script doesn't add any new instrumentation — it just points Langfuse's own
Metrics/Dashboards API (still "unstable" in the SDK, but functional) at that
existing observation data, so p50/p95/p99 latency is visible directly in the
Langfuse UI instead of only in `rca latency-report` or the dashboard's own
"Investigation latency" section.

Idempotent: re-running syncs widgets/the dashboard to match WIDGETS below
(matched by name) rather than duplicating them, and removes any placement
left over from a widget that's since been renamed or dropped from the list.

Usage: python3 scripts/setup_langfuse_latency_dashboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langfuse import Langfuse  # noqa: E402
from langfuse.api.unstable.dashboard_widgets.types.dashboard_widget_chart_type import (  # noqa: E402
    DashboardWidgetChartType,
)
from langfuse.api.unstable.dashboard_widgets.types.dashboard_widget_dimension import (  # noqa: E402
    DashboardWidgetDimension,
)
from langfuse.api.unstable.dashboard_widgets.types.dashboard_widget_filter import (  # noqa: E402
    DashboardWidgetFilter,
)
from langfuse.api.unstable.dashboard_widgets.types.dashboard_widget_metric import (  # noqa: E402
    DashboardWidgetMetric,
)
from langfuse.api.unstable.dashboard_widgets.types.dashboard_widget_view import (  # noqa: E402
    DashboardWidgetView,
)
from langfuse.api.unstable.dashboards.types.create_dashboard_placement_request import (  # noqa: E402
    CreateDashboardPlacementRequest_Widget,
)

from rca.config import settings  # noqa: E402

DASHBOARD_NAME = "RCA Pipeline Latency"

# One row per topic; one widget per percentile in that row (never mixed into
# the same chart), generated below. Each widget carries exactly one metric.
_BASE_WIDGETS = [
    dict(
        base_name="End-to-end vs. LLM narration latency",
        description="The full investigate pipeline (detect->decompose->drill-down->narrate) vs. just the LLM "
        "narration sub-step. Separated because they have very different tail behavior: the ClickHouse "
        "side stays fast even at p99, the LLM step occasionally spikes on free-tier rate-limit retries.",
        dimensions=[DashboardWidgetDimension(field="name")],
        filters=[DashboardWidgetFilter(column="name", operator="any of", value=["investigate", "narrate"], type="stringOptions")],
        chart_type=DashboardWidgetChartType.HORIZONTAL_BAR,
        aggs=["p50", "p95", "p99"],
    ),
    dict(
        base_name="ClickHouse pipeline stages",
        description="window_aggregate (baseline+current), decompose_revenue: the deterministic query stages "
        "that do the actual root-cause analysis, no LLM involved.",
        dimensions=[DashboardWidgetDimension(field="name")],
        filters=[DashboardWidgetFilter(
            column="name", operator="any of",
            value=["window_aggregate[baseline]", "window_aggregate[current]", "decompose_revenue"],
            type="stringOptions",
        )],
        chart_type=DashboardWidgetChartType.HORIZONTAL_BAR,
        aggs=["p95", "p99"],
    ),
    dict(
        base_name="Drill-down latency by factor",
        description="drill_down[<factor>] spans, grouped by which factor was being drilled into.",
        dimensions=[DashboardWidgetDimension(field="name")],
        filters=[DashboardWidgetFilter(column="name", operator="contains", value="drill_down", type="string")],
        chart_type=DashboardWidgetChartType.HORIZONTAL_BAR,
        aggs=["p95", "p99"],
    ),
    dict(
        base_name="Investigation latency trend",
        description="End-to-end investigate latency over time, so a live demo can show it staying stable "
        "(or show exactly when a rate-limit-driven spike happened).",
        dimensions=[],
        filters=[DashboardWidgetFilter(column="name", operator="=", value="investigate", type="string")],
        chart_type=DashboardWidgetChartType.LINE_TIME_SERIES,
        aggs=["p95", "p99"],
    ),
]

WIDGETS = []
for _base in _BASE_WIDGETS:
    _base = dict(_base)
    _aggs = _base.pop("aggs")
    _base_name = _base.pop("base_name")
    for _agg in _aggs:
        WIDGETS.append(dict(
            name=f"{_base_name} — {_agg} (ms)",
            metrics=[DashboardWidgetMetric(measure="latency", agg=_agg)],
            **_base,
        ))


def main() -> None:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        print("LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY not set in .env — nothing to do.")
        sys.exit(1)

    lf = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    existing_widgets_by_name = {w.name: w for w in lf.api.unstable.dashboard_widgets.list(limit=100).data}
    wanted_names = {spec["name"] for spec in WIDGETS}
    widget_ids = []
    for spec in WIDGETS:
        spec = dict(spec)
        if spec["name"] in existing_widgets_by_name:
            w = lf.api.unstable.dashboard_widgets.update(widget_id=existing_widgets_by_name[spec["name"]].id, **spec)
            print(f"  Synced widget: {w.name} (id={w.id})")
        else:
            kwargs = dict(view=DashboardWidgetView.OBSERVATIONS, **spec)
            w = lf.api.unstable.dashboard_widgets.create(**kwargs)
            print(f"  Created widget: {w.name} (id={w.id})")
        widget_ids.append(w.id)

    existing_dashboards = {d.name: d for d in lf.api.unstable.dashboards.list(limit=100).data}
    if DASHBOARD_NAME in existing_dashboards:
        dash = existing_dashboards[DASHBOARD_NAME]
        print(f"Dashboard already exists, reusing: {dash.name} (id={dash.id})")
    else:
        dash = lf.api.unstable.dashboards.create(
            name=DASHBOARD_NAME,
            description="p50/p95/p99 latency for the automated root-cause pipeline, computed by Langfuse "
            "directly from the Tracer spans every investigate/scan run emits.",
        )
        print(f"Created dashboard: {dash.name} (id={dash.id})")

    dash = lf.api.unstable.dashboards.get(dashboard_id=dash.id)
    placements = [p for p in dash.definition.widgets if getattr(p, "widget_id", None)]
    placed_widget_ids = {p.widget_id for p in placements}

    # Remove placements left over from a since-renamed widget (e.g. the old
    # "... p95 latency" widgets, superseded by the "... p95/p99" ones above),
    # and delete the now-orphaned widget itself. Scoped to only widgets this
    # dashboard is actually placing, never anything else in the project.
    existing_widgets_by_id = {w.id: w for w in existing_widgets_by_name.values()}
    for p in placements:
        w = existing_widgets_by_id.get(p.widget_id)
        if w is not None and w.name not in wanted_names:
            lf.api.unstable.dashboards.delete_placement(dashboard_id=dash.id, placement_id=p.id)
            lf.api.unstable.dashboard_widgets.delete(widget_id=w.id)
            print(f"  Removed superseded widget: {w.name}")
            placed_widget_ids.discard(w.id)

    cols, col_width, row_height = 3, 4, 6
    x, y = 0, 0
    for wid in widget_ids:
        if wid in placed_widget_ids:
            continue
        lf.api.unstable.dashboards.add_placement(
            dashboard_id=dash.id,
            request=CreateDashboardPlacementRequest_Widget(widget_id=wid, x=x, y=y, width=col_width, height=row_height),
        )
        x += col_width
        if x >= cols * col_width:
            x = 0
            y += row_height
        print(f"  Placed widget {wid} on dashboard")

    project_id = lf.api.projects.get().data[0].id
    print(f"\nDone: {settings.langfuse_host}/project/{project_id}/dashboards/{dash.id}")


if __name__ == "__main__":
    main()
