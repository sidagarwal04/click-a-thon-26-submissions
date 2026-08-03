"""Metric and dimension definitions, matching metrics_glossary.md exactly.

Every ratio metric is defined as a numerator/denominator pair of ClickHouse sum
expressions, so it is always aggregated as sum/sum (never averaged per-row or
per-day), per the glossary's explicit warning about rollup correctness.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    name: str
    numerator: str
    denominator: str
    is_ratio: bool


METRICS: dict[str, Metric] = {
    "requests": Metric("requests", "count()", "1", is_ratio=False),
    "fills": Metric("fills", "sum(is_filled)", "1", is_ratio=False),
    "fill_rate": Metric("fill_rate", "sum(is_filled)", "count()", is_ratio=True),
    "impressions": Metric("impressions", "sum(is_impression)", "1", is_ratio=False),
    "render_rate": Metric("render_rate", "sum(is_impression)", "sum(is_filled)", is_ratio=True),
    "clicks": Metric("clicks", "sum(is_click)", "1", is_ratio=False),
    "ctr": Metric("ctr", "sum(is_click)", "sum(is_impression)", is_ratio=True),
    "revenue": Metric("revenue", "sum(revenue)", "1", is_ratio=False),
    "ecpm": Metric("ecpm", "sum(revenue) * 1000", "sum(is_impression)", is_ratio=True),
}

# The revenue identity's four multiplicative factors (see metrics_glossary.md):
# revenue = requests * fill_rate * render_rate * (ecpm / 1000)
REVENUE_FACTORS = ["requests", "fill_rate", "render_rate", "ecpm"]

# Dimensions available for drill-down, in the denormalized fact_events table.
# This is an explicit allow-list: these names are interpolated directly into
# SQL identifiers, so only names from this list may ever be used that way.
DIMENSIONS: list[str] = [
    "ad_format",
    "category",
    "publisher_tier",
    "vertical",
    "campaign_type",
    "region",
    "country",
    "device_model",
    "os_version",
]


def metric_value_expr(metric: Metric) -> str:
    """A single expression for the metric's own value (e.g. for daily series)."""
    if metric.is_ratio:
        return f"({metric.numerator}) / nullIf(({metric.denominator}), 0)"
    return metric.numerator
