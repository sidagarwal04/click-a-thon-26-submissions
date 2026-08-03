"""Glossary-aligned metric helpers (sum/sum only — never avg of ratios)."""

from __future__ import annotations

from typing import Any


def fill_rate(fills: float, requests: float) -> float | None:
    if not requests:
        return None
    return fills / requests


def ctr(clicks: float, impressions: float) -> float | None:
    if not impressions:
        return None
    return clicks / impressions


def ecpm(revenue: float, impressions: float) -> float | None:
    if not impressions:
        return None
    return revenue / impressions * 1000.0


def rpr(revenue: float, requests: float) -> float | None:
    if not requests:
        return None
    return revenue / requests


def enrich_counts(row: dict[str, Any]) -> dict[str, Any]:
    """Add rate fields to a counts row with requests/fills/impressions/clicks/revenue."""
    out = dict(row)
    req = float(row.get("requests") or 0)
    fills = float(row.get("fills") or 0)
    imp = float(row.get("impressions") or 0)
    clicks = float(row.get("clicks") or 0)
    rev = float(row.get("revenue") or 0)
    out["fill_rate"] = fill_rate(fills, req)
    out["ctr"] = ctr(clicks, imp)
    out["ecpm"] = ecpm(rev, imp)
    out["rpr"] = rpr(rev, req)
    return out


# Detection thresholds (from EDA quiet-day noise floor)
THRESH_REQ_CHG = 0.15
THRESH_FILL_CHG = 0.015
THRESH_ECPM_CHG = 0.04
THRESH_REV_CHG = 0.03
