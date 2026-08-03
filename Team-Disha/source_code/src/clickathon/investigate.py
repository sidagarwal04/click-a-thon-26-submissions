"""End-to-end investigation → findings JSON (numbers from ClickHouse only)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from clickathon.decompose import decompose_factors
from clickathon.detect import daily_wow, scan_range, _parse_day
from clickathon.drilldown import localize
from clickathon.metrics import THRESH_FILL_CHG
from clickathon.narrate import narrate_findings
from clickathon.telemetry import flush_telemetry, investigation_span

# Hidden segment fill (EDA incident D): global quiet, combo loud
_HIDDEN_FILL_CHG = 0.10
_HIDDEN_FILL_IMPACT = 1500.0


def investigate(day: str | date, *, narrate: bool = True) -> dict[str, Any]:
    """Full RCA pipeline for one day. Returns findings (+ optional narrative)."""
    d = _parse_day(day)
    with investigation_span("investigate", metadata={"day": str(d)}):
        wow = daily_wow(d)
        factors = decompose_factors(d)
        primary = factors.get("primary_factor")

        # Always evaluate fill localization — catches hidden OS×region fills
        loc_fill = localize(d, primary_factor="fill_rate")
        top_fill = loc_fill.get("top_localization") or {}
        hidden_fill = (
            (top_fill.get("fill_chg") or 0) <= -_HIDDEN_FILL_CHG
            and (top_fill.get("fill_impact") or 0) >= _HIDDEN_FILL_IMPACT
            and abs((wow.get("deltas") or {}).get("fill_chg") or 0) < THRESH_FILL_CHG
        )
        if hidden_fill and primary != "requests":
            factors = {
                **factors,
                "primary_factor": "fill_rate",
                "hidden_segment_override": True,
            }
            primary = "fill_rate"
            loc = loc_fill
        else:
            loc = (
                loc_fill
                if primary == "fill_rate"
                else localize(d, primary_factor=primary)
            )

        top = loc.get("top_localization")
        diagnosis: dict[str, Any] = {
            "primary_factor": factors.get("primary_factor"),
            "shape": loc.get("shape"),
            "segment": None,
            "evidence": {},
        }
        if factors.get("primary_factor") == "requests" and loc.get("shape") == "global_uniform":
            diagnosis["segment"] = "ALL (global volume)"
            diagnosis["summary_key"] = "global_request_volume"
        elif top:
            diagnosis["segment"] = top.get("segment") or top.get("dim")
            diagnosis["evidence"] = {
                "source": top.get("source"),
                "fill_chg": top.get("fill_chg"),
                "ecpm_chg": top.get("ecpm_chg"),
                "d_rev": top.get("d_rev"),
                "fill_t": top.get("fill_t"),
                "fill_b": top.get("fill_b"),
                "req_t": top.get("req_t"),
            }
            diagnosis["summary_key"] = "localized_segment"

        ruled_out = list(factors.get("ruled_out_factors") or [])
        ruled_out.append("weekend_seasonality_via_same_dow_baseline")
        if factors.get("primary_factor") == "fill_rate":
            ruled_out.append("advertiser_dims_for_fill_selection_bias")

        findings: dict[str, Any] = {
            "schema_version": "1.0",
            "day": str(d),
            "baseline_day": wow.get("baseline_day"),
            "baseline_rule": "same_dow_minus_7",
            "database": "eda",
            "detection": {
                "is_anomaly": wow.get("is_anomaly"),
                "flags": wow.get("flags"),
                "deltas": wow.get("deltas"),
                "actual": wow.get("actual"),
                "baseline": wow.get("baseline"),
            },
            "decomposition": {
                "identity": factors.get("identity"),
                "primary_factor": factors.get("primary_factor"),
                "contribution_shares": factors.get("contribution_shares"),
                "relative_factor_moves": factors.get("relative_factor_moves"),
            },
            "localization": {
                "shape": loc.get("shape"),
                "top": top,
                "top5": loc.get("top5"),
            },
            "ruled_out": ruled_out,
            "diagnosis": diagnosis,
        }

        if narrate:
            findings["narrative"] = narrate_findings(findings)

        flush_telemetry()
        return findings


def investigate_json(day: str, *, narrate: bool = True) -> str:
    return json.dumps(investigate(day, narrate=narrate), default=str, indent=2)


def scan_anomalies(start: str | None = None, end: str | None = None) -> dict[str, Any]:
    """Scan wow anomalies. Omit start/end (or pass empty) to cover all loaded days."""
    from clickathon.detect import data_date_bounds

    bounds = data_date_bounds()
    s = (start or "").strip() or bounds["start"]
    e = (end or "").strip() or bounds["end"]
    with investigation_span("investigate.scan", metadata={"start": s, "end": e}):
        hits = scan_range(s, e)
        flush_telemetry()
        return {
            "start": s,
            "end": e,
            "data_bounds": bounds,
            "scanned_all": not bool((start or "").strip() or (end or "").strip()),
            "count": len(hits),
            "anomalies": [
                {
                    "day": h["day"],
                    "flags": h["flags"],
                    "deltas": h["deltas"],
                    "n_flags": h["n_flags"],
                }
                for h in hits
            ],
        }
