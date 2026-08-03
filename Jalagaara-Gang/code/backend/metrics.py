"""Shared metric utilities — the ONE place metric formulas live. Import and call like a library.

Two flavors, matching the architecture:
  * SQL builders  -> ClickHouse expressions to drop into query strings (analysis runs in the DB).
  * Python compute -> ratios over ALREADY-AGGREGATED components (never over raw event rows).

Formulas follow InMobi/metrics_glossary.md; column mappings come from config.json["metrics"].
`source` selects the columns: "events" (raw events_enriched) or "rollup" (metrics_hourly).
"""
from __future__ import annotations

from typing import Literal

from config import config

Source = Literal["events", "rollup"]
_M = config()["metrics"]


def _base(source: Source) -> dict[str, str]:
    return _M["base_events"] if source == "events" else _M["base_rollup"]


# ---- SQL builders (ratios are sum/sum, divide-by-zero guarded with nullIf) ----

def base_sql(name: str, source: Source = "events") -> str:
    return _base(source)[name]


def ratio_sql(name: str, source: Source = "events") -> str:
    num, den = _M["ratios"][name]
    b = _base(source)
    return f"{b[num]} / nullIf({b[den]}, 0)"


def ecpm_sql(source: Source = "events") -> str:
    b = _base(source)
    return f"{b['revenue']} / nullIf({b['impressions']}, 0) * {_M['ecpm_multiplier']}"


def metric_sql(name: str, source: Source = "events") -> str:
    """Full ClickHouse expression for any known metric — one call site for every formula."""
    if name in _base(source):
        return base_sql(name, source)
    if name == "ecpm":
        return ecpm_sql(source)
    if name in _M["ratios"]:
        return ratio_sql(name, source)
    raise KeyError(f"unknown metric: {name}")


# ---- Python compute (already-aggregated scalars only) ----

def safe_div(numer: float, denom: float) -> float:
    return numer / denom if denom else 0.0


def fill_rate(fills: float, requests: float) -> float:
    return safe_div(fills, requests)


def render_rate(impressions: float, fills: float) -> float:
    return safe_div(impressions, fills)


def ctr(clicks: float, impressions: float) -> float:
    return safe_div(clicks, impressions)


def ecpm(revenue: float, impressions: float) -> float:
    return safe_div(revenue, impressions) * _M["ecpm_multiplier"]


def rpr(revenue: float, requests: float) -> float:
    return safe_div(revenue, requests)


def revenue_from_identity(requests: float, fill_rate_value: float, ecpm_value: float) -> float:
    """Revenue ~= Requests x FillRate x eCPM/1000 — the decomposition backbone (Lane B)."""
    return requests * fill_rate_value * ecpm_value / _M["ecpm_multiplier"]
