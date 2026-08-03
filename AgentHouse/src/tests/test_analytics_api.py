"""Unit tests for LibreChat analytics catalog, cache, shaping, and models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conversation_agent import cache as analytics_cache
from conversation_agent.catalog import (
    catalog_prompt_blurb,
    list_dimensions,
    list_metrics,
    resolve_dimension,
    resolve_metric,
)
from conversation_agent.clickhouse_client import validate_select_sql
from conversation_agent.data_plane import (
    _shape_contributor_rows,
    _shape_pivot_rows,
    _shape_trend_rows,
    build_contributor_sql,
    build_dimension_values_sql,
    build_pivot_sql,
    build_trend_sql,
)
from conversation_agent.models import (
    AnalyticsDataPayload,
    AnalyticsInsightBlock,
    AnalyticsMetric,
    AnalyticsQueryResponse,
    AnalyticsTextBlock,
)


def test_catalog_aliases():
    assert resolve_dimension("country").column == "geoip_country_code"
    assert resolve_dimension("channel").column == "device_type"
    assert "JSONExtractFloat(payload" in resolve_metric("revenue").expression
    assert resolve_metric("users").table == "activity_events"
    assert list_dimensions()
    assert list_metrics()
    assert "Allowed dimensions" in catalog_prompt_blurb()


def test_insight_block_cardinality():
    metric = AnalyticsMetric(metric_name="revenue", metric_label="Revenue")
    AnalyticsInsightBlock(
        insight_type="Trend",
        metrics=[metric],
        dimensions=[],
        fromTime="2026-01-01",
        toTime="2026-06-30",
        timeGrain="MONTHLY",
    )
    with pytest.raises(ValidationError):
        AnalyticsInsightBlock(
            insight_type="Ranking",
            metrics=[metric],
            dimensions=[],
            fromTime="2026-01-01",
            toTime="2026-06-30",
            timeGrain="MONTHLY",
        )
    with pytest.raises(ValidationError):
        AnalyticsInsightBlock(
            insight_type="Pivot",
            metrics=[metric],
            dimensions=["country"],
            fromTime="2026-01-01",
            toTime="2026-06-30",
            timeGrain="MONTHLY",
        )
    AnalyticsInsightBlock(
        insight_type="Funnel",
        metrics=[
            AnalyticsMetric(metric_name="a", metric_label="A"),
            AnalyticsMetric(metric_name="b", metric_label="B"),
        ],
        dimensions=[],
        fromTime="2026-01-01",
        toTime="2026-06-30",
        timeGrain="WEEKLY",
    )


def test_sql_builders_parse():
    metric = resolve_metric("users")
    assert metric is not None
    payload = AnalyticsDataPayload(
        fromtime="2026-01-01",
        totime="2026-06-30",
        metric_name="users",
        timegrain="month",
        dimensions=["country"],
        filters=[],
    )
    trend = build_trend_sql(payload, metric=metric, grain="month")
    validate_select_sql(trend)
    contrib = build_contributor_sql(
        payload, metric=metric, dim_column="geoip_country_code"
    )
    validate_select_sql(contrib)
    pivot = build_pivot_sql(
        payload,
        metric=metric,
        row_column="geoip_country_code",
        col_column="device_type",
    )
    validate_select_sql(pivot)
    dims = build_dimension_values_sql(
        table="atlys.activity_events",
        column="geoip_country_code",
        fromtime="2026-01-01",
        totime="2026-06-30",
        filters=None,
    )
    validate_select_sql(dims)


def test_row_shaping():
    from datetime import date

    trend = _shape_trend_rows(
        ["bucket", "revenue"],
        [[date(2026, 1, 1), 1000], [date(2026, 2, 1), 1200]],
        metric_name="revenue",
        grain="month",
        window_end=date(2026, 6, 30),
    )
    assert trend[0] == {
        "fromtime": "2026-01-01",
        "totime": "2026-01-31",
        "revenue": 1000.0,
    }

    contrib = _shape_contributor_rows(
        ["member", "value"],
        [["IN", 120], ["US", 108]],
        fromtime="2026-01-01",
        totime="2026-06-30",
    )
    assert contrib[0]["IN"] == 120.0
    assert contrib[0]["US"] == 108.0

    pivot = _shape_pivot_rows(
        ["row_member", "col_member", "revenue"],
        [["IN", "web", 120]],
        row_dim="country",
        col_dim="channel",
        metric_name="revenue",
    )
    assert pivot[0] == {"country": "IN", "channel": "web", "revenue": 120.0}


def test_cache_roundtrip():
    analytics_cache.clear()
    key = analytics_cache.cache_key("test", {"a": 1})
    assert analytics_cache.get(key) is None
    analytics_cache.set(key, {"ok": True}, ttl_seconds=60)
    assert analytics_cache.get(key) == {"ok": True}
    analytics_cache.clear()
    assert analytics_cache.get(key) is None


def test_query_response_requires_blocks():
    with pytest.raises(ValidationError):
        AnalyticsQueryResponse(blocks=[])
    AnalyticsQueryResponse(
        blocks=[AnalyticsTextBlock(text="No data for that window.")]
    )
