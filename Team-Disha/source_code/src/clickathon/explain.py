"""Detailed RCA packs from precomputed eda.rca_* (numbers only from ClickHouse)."""

from __future__ import annotations

import json
from typing import Any

from clickathon.ch import query_rows
from clickathon.config import get_settings
from clickathon.rca_store import (
    _as_date,
    counterfactual_from_store,
    decompose_day_from_store,
    detect_day_from_store,
    drill_combo_from_store,
    drill_dim_from_store,
    expected_baseline_from_store,
    list_incidents_from_store,
)


def _pct(x: Any, digits: int = 1) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{100.0 * float(x):.{digits}f}%"
    except (TypeError, ValueError):
        return "n/a"


def _pp(x: Any, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{100.0 * float(x):.{digits}f} pp"
    except (TypeError, ValueError):
        return "n/a"


def _f(x: Any, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{float(x):,.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _i(x: Any) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{int(float(x)):,}"
    except (TypeError, ValueError):
        return "n/a"


def _window_days(window_start: str, window_end: str) -> list[dict[str, Any]]:
    rows = query_rows(
        """
        SELECT
          event_date, baseline_day,
          requests, base_requests, fill_rate, base_fill_rate,
          ecpm, base_ecpm, revenue, base_revenue,
          req_chg, fill_chg, ecpm_chg, rev_chg,
          is_anomaly, flag_volume, flag_fill, flag_ecpm, flag_revenue
        FROM rca_daily_wow
        WHERE event_date BETWEEN {ws:Date} AND {we:Date}
        ORDER BY event_date
        """,
        {"ws": window_start, "we": window_end},
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "day": _as_date(r["event_date"]),
                "baseline_day": _as_date(r["baseline_day"]),
                "requests": r["requests"],
                "base_requests": r["base_requests"],
                "fill_rate": r["fill_rate"],
                "base_fill_rate": r["base_fill_rate"],
                "ecpm": r["ecpm"],
                "base_ecpm": r["base_ecpm"],
                "revenue": r["revenue"],
                "base_revenue": r["base_revenue"],
                "req_chg": r["req_chg"],
                "fill_chg": r["fill_chg"],
                "ecpm_chg": r["ecpm_chg"],
                "rev_chg": r["rev_chg"],
                "is_anomaly": bool(r["is_anomaly"]),
                "flags": {
                    "volume": bool(r["flag_volume"]),
                    "fill": bool(r["flag_fill"]),
                    "ecpm": bool(r["flag_ecpm"]),
                    "revenue": bool(r["flag_revenue"]),
                },
            }
        )
    return out


def _top_contributors(day: str, primary: str, *, limit: int = 5) -> dict[str, Any]:
    """Rank segments/combos for the primary factor."""
    dims = ["os_version", "region", "ad_format", "category"]
    by_dim: dict[str, list[dict[str, Any]]] = {}
    for dim in dims:
        segs = drill_dim_from_store(day, dim, limit=limit)["segments"]
        if primary == "fill_rate":
            segs = sorted(segs, key=lambda x: x.get("fill_impact") or 0, reverse=True)
        elif primary == "ecpm":
            segs = sorted(
                segs,
                key=lambda x: abs(x.get("ecpm_chg") or 0) * abs(x.get("d_rev") or 1),
                reverse=True,
            )
        else:
            segs = sorted(segs, key=lambda x: abs(x.get("req_chg") or 0), reverse=True)
        by_dim[dim] = segs[:limit]

    combos = {
        "os_region": drill_combo_from_store(day, "os_region", limit=limit)["segments"],
        "format_region": drill_combo_from_store(day, "format_region", limit=limit)["segments"],
    }
    for k, segs in combos.items():
        if primary == "fill_rate":
            combos[k] = sorted(segs, key=lambda x: x.get("fill_impact") or 0, reverse=True)[:limit]
        elif primary == "ecpm":
            combos[k] = sorted(
                segs,
                key=lambda x: abs(x.get("ecpm_chg") or 0) * abs(x.get("d_rev") or 1),
                reverse=True,
            )[:limit]
        else:
            combos[k] = sorted(segs, key=lambda x: abs(x.get("req_chg") or 0), reverse=True)[:limit]

    flat: list[dict[str, Any]] = []
    for dim, segs in by_dim.items():
        for s in segs[:3]:
            flat.append({**s, "kind": "dim", "dimension": dim})
    for combo, segs in combos.items():
        for s in segs[:3]:
            flat.append({**s, "kind": "combo", "dimension": combo})
    if primary == "fill_rate":
        flat.sort(key=lambda x: x.get("fill_impact") or 0, reverse=True)
    elif primary == "ecpm":
        flat.sort(
            key=lambda x: abs(x.get("ecpm_chg") or 0) * abs(x.get("d_rev") or 1),
            reverse=True,
        )
    else:
        flat.sort(key=lambda x: abs(x.get("req_chg") or 0), reverse=True)

    return {"by_dimension": by_dim, "by_combo": combos, "top_overall": flat[:8]}


def _format_seg_line(s: dict[str, Any], primary: str) -> str:
    label = s.get("segment") or f"{s.get('dimension')}={s.get('dim_value') or s.get('dim')}"
    if primary == "fill_rate":
        return (
            f"- {label}: fill {_f(s.get('fill_t'), 3)} vs {_f(s.get('fill_b'), 3)} "
            f"(Δ {_pp(s.get('fill_chg'))}, fill_impact {_f(s.get('fill_impact'), 0)}, "
            f"Δrev {_f(s.get('d_rev'), 2)})"
        )
    if primary == "ecpm":
        return (
            f"- {label}: eCPM {_f(s.get('ecpm_t'), 2)} vs {_f(s.get('ecpm_b'), 2)} "
            f"(Δ {_pct(s.get('ecpm_chg'))}, Δrev {_f(s.get('d_rev'), 2)})"
        )
    return (
        f"- {label}: req Δ {_pct(s.get('req_chg'))}, "
        f"Δrev {_f(s.get('d_rev'), 2)}"
    )


def build_detailed_explanation(
    *,
    day: str,
    baseline_day: str,
    window_start: str,
    window_end: str,
    primary: str,
    shape: str,
    segment: str,
    hidden: bool,
    actual: dict[str, Any],
    baseline: dict[str, Any],
    deltas: dict[str, Any],
    shares: dict[str, Any],
    rel: dict[str, Any] | None,
    seg_ev: dict[str, Any],
    contributors: dict[str, Any],
    window_days: list[dict[str, Any]],
    ruled_out: list[str],
    counterfactual: dict[str, Any] | None = None,
    ml_expected: dict[str, Any] | None = None,
) -> str:
    """Multi-section RCA text grounded only in provided numbers."""
    parts: list[str] = []
    parts.append(
        f"## Diagnosis\n"
        f"On **{day}** vs same-weekday baseline **{baseline_day}** (T-7): "
        f"primary factor is **{primary}**"
        + (f" localized to **{segment}**." if segment and segment not in ("ALL", "global", "") else ".")
        + f" Shape: **{shape}**"
        + (" (global move is muted; segment scan required)." if hidden else ".")
    )

    parts.append(
        f"## Global WoW (probe day)\n"
        f"- Requests: {_i(actual.get('requests'))} vs {_i(baseline.get('requests'))} ({_pct(deltas.get('req_chg'))})\n"
        f"- Fill rate: {_f(actual.get('fill_rate'), 4)} vs {_f(baseline.get('fill_rate'), 4)} "
        f"({_pp(deltas.get('fill_chg'))})\n"
        f"- eCPM: {_f(actual.get('ecpm'), 2)} vs {_f(baseline.get('ecpm'), 2)} ({_pct(deltas.get('ecpm_chg'))})\n"
        f"- Revenue: {_f(actual.get('revenue'), 2)} vs {_f(baseline.get('revenue'), 2)} ({_pct(deltas.get('rev_chg'))})"
    )

    ml = ml_expected if isinstance(ml_expected, dict) and not ml_expected.get("error") else None
    if ml:
        rev = ml.get("revenue") or {}
        fill = ml.get("fill_rate") or {}
        req = ml.get("requests") or {}
        parts.append(
            "## Expected baseline (ClickHouse simpleLinearRegression)\n"
            "Model: actual = slope * T-7 + intercept (trained in SQL).\n"
            f"- Revenue: actual {_f(rev.get('actual'), 2)} vs expected {_f(rev.get('expected'), 2)} "
            f"(residual {_f(rev.get('residual'), 2)}, z={_f(rev.get('residual_z'), 2)})\n"
            f"- Fill: actual {_f(fill.get('actual'), 4)} vs expected {_f(fill.get('expected'), 4)} "
            f"(z={_f(fill.get('residual_z'), 2)})\n"
            f"- Requests: actual {_i(req.get('actual'))} vs expected {_i(req.get('expected'))} "
            f"(z={_f(req.get('residual_z'), 2)})\n"
            f"- ML outlier flag: **{bool(ml.get('ml_outlier'))}** (|z| >= 2 on any metric)."
        )

    if shares:
        parts.append(
            f"## Factor decomposition (revenue identity)\n"
            f"Revenue ≈ Requests × Fill × eCPM / 1000. Contribution shares on the probe day: "
            f"requests {_pct(shares.get('requests'))}, "
            f"fill_rate {_pct(shares.get('fill_rate'))}, "
            f"eCPM {_pct(shares.get('ecpm'))}."
            + (
                f" Relative moves: req {_pct((rel or {}).get('requests'))}, "
                f"fill {_pct((rel or {}).get('fill_rate'))}, "
                f"eCPM {_pct((rel or {}).get('ecpm'))}."
                if rel
                else ""
            )
        )

    if seg_ev:
        parts.append(
            f"## Primary localization\n"
            f"Segment **{seg_ev.get('segment') or segment}** "
            f"(dimension `{seg_ev.get('dimension', '')}` = `{seg_ev.get('dim_value', '')}`):\n"
            f"- Requests: {_i(seg_ev.get('req_t'))} vs {_i(seg_ev.get('req_b'))} ({_pct(seg_ev.get('req_chg'))})\n"
            f"- Fill: {_f(seg_ev.get('fill_t'), 4)} vs {_f(seg_ev.get('fill_b'), 4)} ({_pp(seg_ev.get('fill_chg'))})\n"
            f"- eCPM: {_f(seg_ev.get('ecpm_t'), 2)} vs {_f(seg_ev.get('ecpm_b'), 2)} ({_pct(seg_ev.get('ecpm_chg'))})\n"
            f"- Δ revenue: {_f(seg_ev.get('d_rev'), 2)}; fill_impact: {_f(seg_ev.get('fill_impact'), 0)}"
        )

    top = (contributors or {}).get("top_overall") or []
    if top:
        lines = [_format_seg_line(s, primary) for s in top[:6]]
        parts.append("## Supporting segments (ranked)\n" + "\n".join(lines))

    if window_days and len(window_days) > 1:
        wlines = []
        for w in window_days:
            wlines.append(
                f"- {w['day']}: rev {_pct(w.get('rev_chg'))}, "
                f"req {_pct(w.get('req_chg'))}, fill {_pp(w.get('fill_chg'))}, "
                f"eCPM {_pct(w.get('ecpm_chg'))}"
                + (" ★anomaly" if w.get("is_anomaly") else "")
            )
        parts.append(
            f"## Incident window {window_start}…{window_end}\n" + "\n".join(wlines)
        )
    else:
        parts.append(f"## Incident window\n{window_start}…{window_end} ({len(window_days) or 1} day(s)).")

    cf = counterfactual if isinstance(counterfactual, dict) and not counterfactual.get("error") else None
    if cf:
        parts.append(
            "## Counterfactual (ClickHouse)\n"
            f"Actual revenue {_f(cf.get('revenue_actual'), 2)}. "
            f"If fill stayed at baseline: {_f(cf.get('revenue_if_fill_at_baseline'), 2)} "
            f"(delta {_f(cf.get('delta_if_fill_fixed'), 2)}). "
            f"If eCPM stayed at baseline: {_f(cf.get('revenue_if_ecpm_at_baseline'), 2)} "
            f"(delta {_f(cf.get('delta_if_ecpm_fixed'), 2)}). "
            f"If requests stayed at baseline: {_f(cf.get('revenue_if_requests_at_baseline'), 2)} "
            f"(delta {_f(cf.get('delta_if_requests_fixed'), 2)}). "
            f"Primary-factor explained delta: {_f(cf.get('delta_explained_by_primary'), 2)}. "
            f"Identity: {cf.get('identity') or 'Revenue ~= Requests * Fill * eCPM / 1000'}."
        )
        cf_ruled = list(cf.get("ruled_out_factors") or [])
        if cf_ruled:
            parts.append(
                "## Counterfactual ruled-out factors\n"
                + ", ".join(f"`{r}`" for r in cf_ruled)
                + " (small counterfactual delta vs primary)."
            )

    if ruled_out:
        parts.append("## Ruled out\n" + ", ".join(f"`{r}`" for r in ruled_out))

    parts.append(
        "## Method\n"
        "Baseline = same weekday -7. Ratios are sum/sum. "
        "Signals/incidents/counterfactuals assembled in ClickHouse SQL "
        "(`eda.rca_*`, dictionaries, seasonality z-scores, "
        "simpleLinearRegression expected baselines)."
    )
    return "\n\n".join(parts)


def explain_anomaly_from_store(
    *,
    incident_id: str = "",
    probe_day: str = "",
    include_narrative: bool = True,
) -> dict[str, Any]:
    """Full RCA card for one incident (by id) or probe day."""
    settings = get_settings()
    bag = list_incidents_from_store()
    incidents = list(bag.get("incidents") or [])
    hit: dict[str, Any] | None = None
    if incident_id:
        hit = next((i for i in incidents if str(i.get("id")) == str(incident_id)), None)
        if not hit:
            return {"error": f"incident_id {incident_id!r} not found in rca_incidents"}
    elif probe_day:
        day = str(probe_day)[:10]
        cands = [
            i
            for i in incidents
            if _as_date(i.get("probe_day")) == day
            or (
                _as_date(i.get("window_start")) <= day <= _as_date(i.get("window_end"))
            )
        ]
        if not cands:
            # Still allow day RCA without a clustered incident
            hit = None
            day_only = day
        else:
            hit = max(cands, key=lambda x: float(x.get("severity") or 0))
            day_only = _as_date(hit["probe_day"])
    else:
        return {
            "error": "pass incident_id (e.g. 'A') or probe_day (YYYY-MM-DD)",
            "available_ids": [i.get("id") for i in incidents],
        }

    if hit:
        day = _as_date(hit["probe_day"])
        ws, we = _as_date(hit["window_start"]), _as_date(hit["window_end"])
        primary = str(hit.get("primary_factor") or "requests")
        shape = str(hit.get("shape") or "")
        segment = str(hit.get("segment") or "")
        hidden = bool(hit.get("hidden_globally"))
        evidence = hit.get("evidence") or {}
        actual = evidence.get("actual") or {}
        baseline = evidence.get("baseline") or {}
        seg_ev = evidence.get("segment") or {}
        deltas = hit.get("global_deltas") or {}
        shares = hit.get("contribution_shares") or {}
        ruled = list(hit.get("ruled_out") or [])
        baseline_day = _as_date(hit.get("baseline_day"))
        severity = hit.get("severity")
        iid = hit.get("id")
    else:
        day = day_only  # type: ignore[name-defined]
        wow = detect_day_from_store(day)
        if wow.get("error"):
            return wow
        fac = decompose_day_from_store(day)
        primary = str(fac.get("primary_factor") or "requests")
        actual, baseline = wow.get("actual") or {}, wow.get("baseline") or {}
        deltas = wow.get("deltas") or {}
        shares = fac.get("contribution_shares") or {}
        ws = we = day
        shape, segment, hidden = "from_store", "", False
        seg_ev, ruled = {}, []
        baseline_day = _as_date(wow.get("baseline_day"))
        severity, iid = None, None

    fac = decompose_day_from_store(day)
    rel = fac.get("relative_factor_moves") or {}
    if not shares:
        shares = fac.get("contribution_shares") or {}
    if not actual:
        wow = detect_day_from_store(day)
        actual = wow.get("actual") or {}
        baseline = wow.get("baseline") or {}
        deltas = wow.get("deltas") or {}
        baseline_day = baseline_day or _as_date(wow.get("baseline_day"))

    contributors = _top_contributors(day, primary)
    if not seg_ev and contributors.get("top_overall"):
        seg_ev = contributors["top_overall"][0]
        segment = segment or str(seg_ev.get("segment") or "")

    if not ruled:
        if primary == "requests":
            ruled = ["fill_rate_as_primary", "ecpm_as_primary", "weekend_seasonality", "single_segment"]
        elif primary == "fill_rate":
            ruled = ["requests_as_primary", "ecpm_as_primary", "advertiser_dims_for_fill"]
        else:
            ruled = ["fill_rate_as_primary", "weekend_seasonality"]

    window_days = _window_days(ws, we)
    cf = counterfactual_from_store(
        incident_id=str(iid or ""),
        probe_day=day if not iid else "",
    )
    ml = expected_baseline_from_store(day)
    explanation = build_detailed_explanation(
        day=day,
        baseline_day=baseline_day,
        window_start=ws,
        window_end=we,
        primary=primary,
        shape=shape,
        segment=segment,
        hidden=hidden,
        actual=actual,
        baseline=baseline,
        deltas=deltas,
        shares=shares,
        rel=rel,
        seg_ev=seg_ev if isinstance(seg_ev, dict) else {},
        contributors=contributors,
        window_days=window_days,
        ruled_out=ruled,
        counterfactual=cf,
        ml_expected=ml,
    )

    pack: dict[str, Any] = {
        "schema_version": "2.2",
        "mode": "detailed_rca",
        "database": settings.clickhouse_rca_database,
        "incident_id": iid,
        "probe_day": day,
        "baseline_day": baseline_day,
        "baseline_rule": "same_dow_minus_7",
        "window_start": ws,
        "window_end": we,
        "primary_factor": primary,
        "shape": shape,
        "segment": segment,
        "hidden_globally": hidden,
        "severity": severity,
        "global_deltas": deltas,
        "contribution_shares": shares,
        "relative_factor_moves": rel,
        "evidence": {"actual": actual, "baseline": baseline, "segment": seg_ev},
        "ml_expected": ml,
        "counterfactual": cf,
        "contributors": contributors,
        "window_days": window_days,
        "ruled_out": ruled,
        "explanation": explanation,
        "short_explanation": (hit.get("explanation") if hit else None),
        "instructions_for_agent": (
            "Present the `explanation` sections in full (Diagnosis → Method). "
            "Include Expected baseline and Counterfactual sections when present. "
            "Quote only numbers from this JSON. Do not invent segments or deltas."
        ),
        "source_tables": [
            "rca_incidents",
            "rca_daily_wow",
            "rca_ml_expected",
            "rca_factor_day",
            "rca_segment_day",
            "rca_combo_day",
            "rca_counterfactual",
        ],
    }

    if include_narrative:
        try:
            from clickathon.narrate import narrate_detailed_rca

            pack["narrative"] = narrate_detailed_rca(pack)
        except Exception as exc:  # noqa: BLE001
            pack["narrative_error"] = str(exc)

    return pack


def enrich_incident_explanation_during_materialize(inc: dict[str, Any]) -> str:
    """Rebuild a detailed explanation string for an assembled incident (materialize)."""
    day = str(inc["probe_day"])[:10]
    ws, we = str(inc["window_start"])[:10], str(inc["window_end"])[:10]
    primary = str(inc.get("primary_factor") or "requests")
    evidence = inc.get("evidence") or {}
    fac = decompose_day_from_store(day)
    contributors = _top_contributors(day, primary, limit=4)
    cf = counterfactual_from_store(incident_id=str(inc.get("id") or ""), probe_day=day)
    ml = expected_baseline_from_store(day)
    return build_detailed_explanation(
        day=day,
        baseline_day=str(inc.get("baseline_day") or "")[:10],
        window_start=ws,
        window_end=we,
        primary=primary,
        shape=str(inc.get("shape") or ""),
        segment=str(inc.get("segment") or ""),
        hidden=bool(inc.get("hidden_globally")),
        actual=evidence.get("actual") or {},
        baseline=evidence.get("baseline") or {},
        deltas=inc.get("global_deltas") or {},
        shares=inc.get("contribution_shares") or fac.get("contribution_shares") or {},
        rel=fac.get("relative_factor_moves"),
        seg_ev=evidence.get("segment") or {},
        contributors=contributors,
        window_days=_window_days(ws, we),
        ruled_out=list(inc.get("ruled_out") or []),
        counterfactual=cf,
        ml_expected=ml,
    )
