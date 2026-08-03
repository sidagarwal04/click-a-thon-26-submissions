import math


def is_invalid_number(x) -> bool:
    """True for None and NaN - ClickHouse's window functions return NaN
    (not NULL) when the trailing window has zero prior rows."""
    return x is None or (isinstance(x, float) and math.isnan(x))


METRIC_EXPRESSIONS = {
    "revenue": "revenue",
    "requests": "requests",
    "fill_rate": "fills / nullIf(requests, 0)",
    "render_rate": "impressions / nullIf(fills, 0)",
    "ecpm": "revenue / nullIf(impressions, 0) * 1000",
    "ctr": "clicks / nullIf(impressions, 0)",
    "rpr": "revenue / nullIf(requests, 0)",
    "fills": "fills",
    "impressions": "impressions",
    "clicks": "clicks",
}

# Scanned as headline anomalies. Excludes raw counts (redundant with the
# rate metrics derived from them) and rpr (= fill_rate x render_rate x ecpm,
# so it never adds signal those three don't already carry).
HEADLINE_METRICS = ["revenue", "fill_rate", "render_rate", "ecpm", "ctr"]

DIMENSIONS = [
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

# Unfilled traffic, not a segment - advertiser_id is '' (not NULL) when
# unfilled, so vertical/campaign_type resolve to '' via the rollup's LEFT JOIN.
BLANK_SEGMENT_VALUE = ""
BLANK_SEGMENT_LABEL = "unfilled traffic (no advertiser attached)"

# (metric, dimension) pairs that cannot vary by construction - an advertiser
# (and therefore vertical/campaign_type) exists only on filled requests.
DEGENERATE_METRIC_DIMENSIONS = {
    ("fill_rate", "vertical"): (
        "fill rate cannot be decomposed by vertical - an advertiser (and therefore a "
        "vertical) exists only on filled requests, so fill rate is 1.0 by construction "
        "inside every vertical"
    ),
    ("fill_rate", "campaign_type"): (
        "fill rate cannot be decomposed by campaign type - a campaign type exists only "
        "on filled requests, so fill rate is 1.0 by construction inside every campaign type"
    ),
}


def scannable_dimensions(metric_name: str) -> list:
    return [d for d in DIMENSIONS if (metric_name, d) not in DEGENERATE_METRIC_DIMENSIONS]


def degenerate_notes(metric_name: str) -> list:
    return [
        f"{dim}: not applicable - {reason}"
        for (m, dim), reason in DEGENERATE_METRIC_DIMENSIONS.items()
        if m == metric_name
    ]
