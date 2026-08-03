"""Dimension / combo contribution drill-down."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from clickathon.ch import query_rows
from clickathon.detect import SEGMENT_SQL, _parse_day, segment_scan
from clickathon.telemetry import investigation_span

COMBO_SQL = {
    "os_region": """
        SELECT g.os_version AS dim1, g.region AS dim2,
          countIf(e.event_date = {d:Date}) AS req_t,
          countIf(e.event_date = {b:Date}) AS req_b,
          sumIf(e.is_filled, e.event_date = {d:Date}) AS fills_t,
          sumIf(e.is_filled, e.event_date = {b:Date}) AS fills_b,
          sumIf(e.revenue, e.event_date = {d:Date}) AS rev_t,
          sumIf(e.revenue, e.event_date = {b:Date}) AS rev_b,
          sumIf(e.is_impression, e.event_date = {d:Date}) AS imp_t,
          sumIf(e.is_impression, e.event_date = {b:Date}) AS imp_b
        FROM ad_events AS e
        LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE e.event_date IN ({d:Date}, {b:Date})
        GROUP BY dim1, dim2
        HAVING req_t > 1000 AND req_b > 1000
    """,
    "format_region": """
        SELECT e.ad_format AS dim1, g.region AS dim2,
          countIf(e.event_date = {d:Date}) AS req_t,
          countIf(e.event_date = {b:Date}) AS req_b,
          sumIf(e.is_filled, e.event_date = {d:Date}) AS fills_t,
          sumIf(e.is_filled, e.event_date = {b:Date}) AS fills_b,
          sumIf(e.revenue, e.event_date = {d:Date}) AS rev_t,
          sumIf(e.revenue, e.event_date = {b:Date}) AS rev_b,
          sumIf(e.is_impression, e.event_date = {d:Date}) AS imp_t,
          sumIf(e.is_impression, e.event_date = {b:Date}) AS imp_b
        FROM ad_events AS e
        LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE e.event_date IN ({d:Date}, {b:Date})
        GROUP BY dim1, dim2
        HAVING imp_t > 800 AND imp_b > 800
    """,
}


def _score_rows(rows: list[dict[str, Any]], combo: bool = False) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for r in rows:
        fill_t = r["fills_t"] / r["req_t"] if r["req_t"] else None
        fill_b = r["fills_b"] / r["req_b"] if r["req_b"] else None
        ecpm_t = r["rev_t"] / r["imp_t"] * 1000 if r["imp_t"] else None
        ecpm_b = r["rev_b"] / r["imp_b"] * 1000 if r["imp_b"] else None
        fill_chg = (fill_t - fill_b) if fill_t is not None and fill_b is not None else 0.0
        ecpm_chg = (ecpm_t - ecpm_b) if ecpm_t is not None and ecpm_b is not None else 0.0
        item: dict[str, Any] = {
            "req_t": int(r["req_t"]),
            "fill_t": fill_t,
            "fill_b": fill_b,
            "fill_chg": fill_chg,
            "ecpm_t": ecpm_t,
            "ecpm_b": ecpm_b,
            "ecpm_chg": ecpm_chg,
            "d_rev": float(r["rev_t"] - r["rev_b"]),
            "fill_impact": abs(fill_chg) * float(r["req_t"]),
        }
        if combo:
            item["dim1"] = r["dim1"]
            item["dim2"] = r["dim2"]
            item["segment"] = f"{r['dim1']} × {r['dim2']}"
        else:
            item["dim"] = r["dim"]
            item["segment"] = str(r["dim"])
        scored.append(item)
    scored.sort(key=lambda x: max(x["fill_impact"], abs(x["d_rev"]) * 50), reverse=True)
    return scored


def drill_dimension(day: str | date, dimension: str, limit: int = 12) -> dict[str, Any]:
    with investigation_span(
        "drill.dimension", metadata={"day": str(_parse_day(day)), "dimension": dimension}
    ):
        return segment_scan(day, dimension=dimension, limit=limit)


def drill_combo(day: str | date, combo: str = "os_region", limit: int = 15) -> dict[str, Any]:
    d = _parse_day(day)
    base = d - timedelta(days=7)
    sql = COMBO_SQL.get(combo)
    if not sql:
        return {"error": f"unknown combo {combo}", "allowed": list(COMBO_SQL)}

    with investigation_span("drill.combo", metadata={"day": str(d), "combo": combo}):
        rows = query_rows(sql, {"d": d, "b": base})
        scored = _score_rows(rows, combo=True)[:limit]
        return {
            "day": str(d),
            "baseline_day": str(base),
            "combo": combo,
            "segments": scored,
            "top_segment": scored[0] if scored else None,
        }


def localize(day: str | date, primary_factor: str | None = None) -> dict[str, Any]:
    """Run priority drills based on primary factor; return top localization."""
    d = _parse_day(day)
    with investigation_span("drill.localize", metadata={"day": str(d), "factor": primary_factor}):
        dims = ["os_version", "ad_format", "region", "category"]
        per_dim = {dim: drill_dimension(d, dim, limit=8) for dim in dims}
        combos = {
            "os_region": drill_combo(d, "os_region", limit=10),
            "format_region": drill_combo(d, "format_region", limit=10),
        }

        candidates: list[dict[str, Any]] = []
        for dim, res in per_dim.items():
            for seg in res.get("segments") or []:
                candidates.append({**seg, "source": dim, "kind": "single"})
        for name, res in combos.items():
            for seg in res.get("segments") or []:
                candidates.append({**seg, "source": name, "kind": "combo"})

        if primary_factor == "fill_rate":
            candidates.sort(key=lambda x: x.get("fill_impact") or 0, reverse=True)
            top = _refine_fill_top(candidates)
        elif primary_factor == "ecpm":
            candidates.sort(
                key=lambda x: abs(x.get("ecpm_chg") or 0) * abs(x.get("d_rev") or 1),
                reverse=True,
            )
            top = candidates[0] if candidates else None
        elif primary_factor == "requests":
            # Global volume: prefer homogeneity signal
            candidates.sort(key=lambda x: abs(x.get("d_rev") or 0), reverse=True)
            top = candidates[0] if candidates else None
        else:
            candidates.sort(
                key=lambda x: max(x.get("fill_impact") or 0, abs(x.get("d_rev") or 0) * 50),
                reverse=True,
            )
            top = candidates[0] if candidates else None

        # Global volume heuristic: if top fill impacts are tiny vs req moves elsewhere
        shape = "localized"
        if primary_factor == "requests":
            shape = "global_uniform"
        elif top and top.get("kind") == "combo" and primary_factor == "fill_rate":
            shape = "hidden_combo"

        return {
            "day": str(d),
            "primary_factor": primary_factor,
            "shape": shape,
            "top_localization": top,
            "top5": candidates[:5],
            "dimensions_scanned": list(SEGMENT_SQL),
            "combos_scanned": list(COMBO_SQL),
        }


def _refine_fill_top(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer a combo when it concentrates a much worse fill drop than the parent dim."""
    if not candidates:
        return None
    top = candidates[0]
    if top.get("kind") == "combo":
        return top
    parent = str(top.get("dim") or top.get("segment") or "")
    combos = [
        c
        for c in candidates
        if c.get("kind") == "combo" and parent and parent in str(c.get("segment") or "")
    ]
    if not combos:
        return top
    best = max(combos, key=lambda c: abs(c.get("fill_chg") or 0))
    # Combo is a real refinement if Δfill is much worse (hidden segment pattern)
    if abs(best.get("fill_chg") or 0) >= abs(top.get("fill_chg") or 0) + 0.15:
        if (best.get("fill_impact") or 0) >= 1000:
            return best
    return top
