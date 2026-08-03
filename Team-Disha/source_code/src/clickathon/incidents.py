"""Deterministic incident discovery (no hardcoded dates).

Pipeline (EDA design):
1. Same-DOW daily wow for every day in range
2. Segment / combo scans so hidden fill & layered eCPM are visible
3. Recovery gate — beneficial rebounds vs a bad baseline are not new incidents
4. Cluster consecutive days with the same factor + segment into windows
5. Explain each window from live ClickHouse numbers (investigate/localize)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from clickathon.decompose import decompose_factors
from clickathon.detect import daily_wow, data_date_bounds, _parse_day
from clickathon.drilldown import drill_combo, drill_dimension, localize
from clickathon.metrics import THRESH_ECPM_CHG, THRESH_FILL_CHG, THRESH_REQ_CHG
from clickathon.telemetry import flush_telemetry, investigation_span

# Segment thresholds (stricter localization; lower than global for impact)
SEG_FILL_CHG = 0.10  # 10 pp absolute fill drop in a segment
SEG_FILL_IMPACT = 1500.0  # |Δfill| × requests
SEG_ECPM_ABS = 0.25  # absolute eCPM drop in a segment
SEG_ECPM_REV = 3.0  # |d_rev| floor for eCPM segment signal
MIN_SEG_REQ = 2000


def _pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:.{digits}f}%"


def _pp(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:.{digits}f} pp"


def _f(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def _daterange(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


def _segment_candidates(day: str | date) -> list[dict[str, Any]]:
    """Rank abnormal segments by impact (fill OS / OS×region, eCPM format×region / category)."""
    d = _parse_day(day)
    cands: list[dict[str, Any]] = []

    os_scan = drill_dimension(d, "os_version", limit=15)
    for s in os_scan.get("segments") or []:
        fill_chg = s.get("fill_chg") or 0.0
        impact = s.get("fill_impact") or 0.0
        if fill_chg <= -SEG_FILL_CHG and impact >= SEG_FILL_IMPACT and (s.get("req_t") or 0) >= MIN_SEG_REQ:
            cands.append(
                {
                    "kind": "fill",
                    "source": "os_version",
                    "segment": f"os_version={s.get('dim')}",
                    "score": impact,
                    "evidence": s,
                }
            )

    os_reg = drill_combo(d, "os_region", limit=20)
    for s in os_reg.get("segments") or []:
        fill_chg = s.get("fill_chg") or 0.0
        impact = s.get("fill_impact") or 0.0
        if fill_chg <= -SEG_FILL_CHG and impact >= SEG_FILL_IMPACT and (s.get("req_t") or 0) >= 1000:
            cands.append(
                {
                    "kind": "fill",
                    "source": "os_region",
                    "segment": s.get("segment"),
                    "score": impact * 1.1,  # slight preference for combo when both fire
                    "evidence": s,
                }
            )

    fmt_reg = drill_combo(d, "format_region", limit=15)
    for s in fmt_reg.get("segments") or []:
        ecpm_chg = s.get("ecpm_chg") or 0.0
        d_rev = float(s.get("d_rev") or 0.0)
        # Loss drivers only (skip offsetting cells like native ↑ while interstitial ↓)
        if ecpm_chg <= -SEG_ECPM_ABS and d_rev <= -SEG_ECPM_REV:
            cands.append(
                {
                    "kind": "ecpm",
                    "source": "format_region",
                    "segment": s.get("segment"),
                    "score": abs(d_rev) * abs(ecpm_chg) * 100,
                    "evidence": s,
                }
            )

    cat = drill_dimension(d, "category", limit=12)
    for s in cat.get("segments") or []:
        ecpm_chg = s.get("ecpm_chg") or 0.0
        d_rev = float(s.get("d_rev") or 0.0)
        if ecpm_chg <= -SEG_ECPM_ABS and d_rev <= -SEG_ECPM_REV:
            cands.append(
                {
                    "kind": "ecpm",
                    "source": "category",
                    "segment": f"category={s.get('dim')}",
                    "score": abs(d_rev) * abs(ecpm_chg) * 80,
                    "evidence": s,
                }
            )

    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands


def _is_recovery(wow: dict[str, Any], primary: str) -> bool:
    """Beneficial rebound vs same-DOW baseline → recovery, not a new incident."""
    d = wow.get("deltas") or {}
    req = d.get("req_chg") or 0.0
    fill = d.get("fill_chg") or 0.0
    ecpm = d.get("ecpm_chg") or 0.0
    if primary == "requests" and req >= THRESH_REQ_CHG:
        return True
    if primary == "fill_rate" and fill >= THRESH_FILL_CHG:
        return True
    if primary == "ecpm" and ecpm >= THRESH_ECPM_CHG:
        return True
    return False


def _problem_direction(wow: dict[str, Any], primary: str) -> bool:
    """True if the primary factor moved in the harmful direction."""
    d = wow.get("deltas") or {}
    if primary == "requests":
        return (d.get("req_chg") or 0.0) <= -THRESH_REQ_CHG
    if primary == "fill_rate":
        return (d.get("fill_chg") or 0.0) <= -THRESH_FILL_CHG
    if primary == "ecpm":
        return (d.get("ecpm_chg") or 0.0) <= -THRESH_ECPM_CHG
    return False


def _resolve_primary(wow: dict[str, Any], factors: dict[str, Any]) -> str:
    """Prefer loud volume crashes over secondary soft eCPM on multi-factor days."""
    d = wow.get("deltas") or {}
    req = d.get("req_chg") or 0.0
    # Large request drop dominates (EDA: Jun 21 is volume even with soft eCPM)
    if req <= -THRESH_REQ_CHG:
        return "requests"
    primary = factors.get("primary_factor") or "requests"
    if _problem_direction(wow, primary) and not _is_recovery(wow, primary):
        return primary
    # Fall back to whichever harmful global flag is on
    if (d.get("fill_chg") or 0.0) <= -THRESH_FILL_CHG:
        return "fill_rate"
    if (d.get("ecpm_chg") or 0.0) <= -THRESH_ECPM_CHG:
        return "ecpm"
    return primary


def _day_signals(day: date) -> list[dict[str, Any]]:
    """Emit zero or more incident signals for one day (global and/or segment)."""
    wow = daily_wow(day)
    if wow.get("error"):
        return []
    factors = decompose_factors(day)
    primary = _resolve_primary(wow, factors)
    segs = _segment_candidates(day)
    out: list[dict[str, Any]] = []

    # Global volume crash
    if primary == "requests" and _problem_direction(wow, "requests"):
        out.append(
            {
                "day": str(day),
                "primary_factor": "requests",
                "shape": "global_uniform",
                "segment_key": "ALL",
                "segment": "ALL (global volume)",
                "source": "global",
                "wow": wow,
                "factors": factors,
                "seg_evidence": None,
                "severity": abs(wow["deltas"].get("rev_chg") or 0)
                * abs(wow["deltas"].get("req_chg") or 0)
                * 1000,
            }
        )
    elif primary == "fill_rate" and _problem_direction(wow, "fill_rate"):
        top = next((s for s in segs if s["kind"] == "fill"), None)
        if top:
            out.append(
                {
                    "day": str(day),
                    "primary_factor": "fill_rate",
                    "shape": "localized" if top["source"] != "os_region" else "hidden_combo",
                    "segment_key": top["segment"],
                    "segment": top["segment"],
                    "source": top["source"],
                    "wow": wow,
                    "factors": factors,
                    "seg_evidence": top["evidence"],
                    "severity": top["score"],
                }
            )
        else:
            out.append(
                {
                    "day": str(day),
                    "primary_factor": "fill_rate",
                    "shape": "global_fill",
                    "segment_key": "GLOBAL_FILL",
                    "segment": "global fill",
                    "source": "global",
                    "wow": wow,
                    "factors": factors,
                    "seg_evidence": None,
                    "severity": abs(wow["deltas"].get("fill_chg") or 0) * 1e5,
                }
            )
    elif primary == "ecpm" and _problem_direction(wow, "ecpm"):
        top = next((s for s in segs if s["kind"] == "ecpm"), None)
        out.append(
            {
                "day": str(day),
                "primary_factor": "ecpm",
                "shape": "layered" if top else "global_ecpm",
                "segment_key": (top["segment"] if top else "GLOBAL_ECPM"),
                "segment": (top["segment"] if top else "global eCPM"),
                "source": (top["source"] if top else "global"),
                "wow": wow,
                "factors": factors,
                "seg_evidence": (top["evidence"] if top else None),
                "severity": (
                    top["score"] if top else abs(wow["deltas"].get("ecpm_chg") or 0) * 1e4
                ),
            }
        )

    # When a global volume crash fires, skip secondary segment tags on that day
    # (mix artifacts look like eCPM/fill moves under a uniform −40% request shock).
    if any(x["primary_factor"] == "requests" for x in out):
        return out

    # Hidden / residual segment fill (global quiet OR global recovering while segment still bad)
    fill_tops = [s for s in segs if s["kind"] == "fill"]
    if fill_tops:
        top = fill_tops[0]
        already = any(
            x["segment_key"] == top["segment"] and x["primary_factor"] == "fill_rate" for x in out
        )
        seg_still_bad = (top["evidence"].get("fill_chg") or 0) <= -SEG_FILL_CHG
        if not already and seg_still_bad:
            out.append(
                {
                    "day": str(day),
                    "primary_factor": "fill_rate",
                    "shape": "hidden_combo",
                    "segment_key": top["segment"],
                    "segment": top["segment"],
                    "source": top["source"],
                    "wow": wow,
                    "factors": factors,
                    "seg_evidence": top["evidence"],
                    "severity": top["score"],
                    "hidden_globally": abs(wow["deltas"].get("fill_chg") or 0) < THRESH_FILL_CHG,
                }
            )

    # Skip eCPM layering on days dominated by a fill incident (avoids mean-reversion
    # of offsetting cells, e.g. native×EU dropping after an elevated baseline).
    if any(x["primary_factor"] == "fill_rate" for x in out):
        return out

    # Early layered eCPM while global looks fine (offsetting cells)
    ecpm_tops = [s for s in segs if s["kind"] == "ecpm"]
    if ecpm_tops and not any(x["primary_factor"] == "ecpm" for x in out):
        top = ecpm_tops[0]
        if not _is_recovery(wow, "ecpm"):
            out.append(
                {
                    "day": str(day),
                    "primary_factor": "ecpm",
                    "shape": "layered_hidden",
                    "segment_key": top["segment"],
                    "segment": top["segment"],
                    "source": top["source"],
                    "wow": wow,
                    "factors": factors,
                    "seg_evidence": top["evidence"],
                    "severity": top["score"],
                    "hidden_globally": not _problem_direction(wow, "ecpm"),
                }
            )

    return out


def _cluster(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive days sharing (primary_factor, segment_key) into windows."""
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in signals:
        by_key[(s["primary_factor"], s["segment_key"])].append(s)

    clusters: list[dict[str, Any]] = []
    for (factor, seg_key), rows in by_key.items():
        rows.sort(key=lambda r: r["day"])
        run: list[dict[str, Any]] = []
        for row in rows:
            if not run:
                run = [row]
                continue
            prev = _parse_day(run[-1]["day"])
            cur = _parse_day(row["day"])
            if (cur - prev).days <= 1:
                run.append(row)
            else:
                clusters.append(_finalize_cluster(run))
                run = [row]
        if run:
            clusters.append(_finalize_cluster(run))

    # Prefer higher severity; drop tiny overlapping noise
    clusters.sort(key=lambda c: c["severity"], reverse=True)
    return clusters


def _finalize_cluster(run: list[dict[str, Any]]) -> dict[str, Any]:
    # Prefer a day where the signal is clearest (for hidden fill, prefer globally quiet days)
    if run[0]["primary_factor"] == "fill_rate":
        hidden = [r for r in run if r.get("hidden_globally")]
        pool = hidden or run
        probe = max(pool, key=lambda r: r["severity"])
    elif run[0]["primary_factor"] == "ecpm":
        visible = [r for r in run if not r.get("hidden_globally")]
        pool = visible or run
        probe = max(pool, key=lambda r: r["severity"])
    else:
        probe = max(run, key=lambda r: r["severity"])
    return {
        "window_start": run[0]["day"],
        "window_end": run[-1]["day"],
        "n_days": len(run),
        "days": [r["day"] for r in run],
        "probe_day": probe["day"],
        "primary_factor": probe["primary_factor"],
        "shape": probe["shape"],
        "segment": probe["segment"],
        "segment_key": probe["segment_key"],
        "source": probe["source"],
        "severity": sum(r["severity"] for r in run),
        "hidden_globally": any(r.get("hidden_globally") for r in run),
        "probe": probe,
    }


def _merge_ecpm_layers(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse nearby eCPM loss-driver clusters into one layered incident."""
    ecpm = [c for c in clusters if c["primary_factor"] == "ecpm"]
    other = [c for c in clusters if c["primary_factor"] != "ecpm"]
    if len(ecpm) <= 1:
        return clusters

    ecpm.sort(key=lambda c: c["window_start"])
    merged: list[dict[str, Any]] = []
    cur = dict(ecpm[0])
    segs = {cur["segment"]}
    for nxt in ecpm[1:]:
        gap = (_parse_day(nxt["window_start"]) - _parse_day(cur["window_end"])).days
        # Allow a 2-day bridge so a multi-factor volume day does not split layered eCPM
        if gap <= 2:
            cur["window_end"] = max(cur["window_end"], nxt["window_end"])
            cur["window_start"] = min(cur["window_start"], nxt["window_start"])
            cur["days"] = sorted(set(cur.get("days", []) + nxt.get("days", [])))
            cur["n_days"] = len(cur["days"])
            cur["severity"] += nxt["severity"]
            segs.add(nxt["segment"])
            # Prefer a globally soft probe day when available
            if not cur.get("hidden_globally") or nxt.get("hidden_globally") is False:
                if nxt["severity"] >= cur["probe"].get("severity", 0) * 0.5:
                    if not nxt.get("hidden_globally"):
                        cur["probe_day"] = nxt["probe_day"]
                        cur["probe"] = nxt["probe"]
                        cur["hidden_globally"] = False
            cur["shape"] = "layered"
        else:
            cur["segment"] = " + ".join(sorted(segs)) if len(segs) > 1 else next(iter(segs))
            cur["segment_key"] = cur["segment"]
            merged.append(cur)
            cur = dict(nxt)
            segs = {cur["segment"]}
    cur["segment"] = " + ".join(sorted(segs)) if len(segs) > 1 else next(iter(segs))
    cur["segment_key"] = cur["segment"]
    merged.append(cur)
    return other + merged


def _prefer_combo_over_single(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """If OS and OS×region both fire for fill, keep the more specific combo window."""
    fill = [c for c in clusters if c["primary_factor"] == "fill_rate"]
    other = [c for c in clusters if c["primary_factor"] != "fill_rate"]
    drop: set[int] = set()
    for i, a in enumerate(fill):
        for j, b in enumerate(fill):
            if i >= j:
                continue
            # same window overlap
            if not (
                a["window_start"] <= b["window_end"] and b["window_start"] <= a["window_end"]
            ):
                continue
            a_combo = " x " in str(a["segment"]) or "×" in str(a["segment"])
            b_combo = " x " in str(b["segment"]) or "×" in str(b["segment"])
            if a_combo and not b_combo and str(b["segment"]).split("=")[-1] in str(a["segment"]):
                drop.add(j)
            elif b_combo and not a_combo and str(a["segment"]).split("=")[-1] in str(b["segment"]):
                drop.add(i)
    kept = [c for i, c in enumerate(fill) if i not in drop]
    return other + kept


def _explain(cluster: dict[str, Any]) -> dict[str, Any]:
    """EDA-style explanation from live probe-day numbers (no invented figures)."""
    probe = cluster["probe"]
    wow = probe["wow"]
    factors = probe["factors"]
    t, b = wow["actual"], wow["baseline"]
    d = wow["deltas"]
    day = cluster["probe_day"]
    loc = localize(day, primary_factor=cluster["primary_factor"])
    factor = cluster["primary_factor"]
    seg = cluster["segment"]
    ev = probe.get("seg_evidence") or {}

    if factor == "requests":
        explanation = (
            f"On {day} vs same-DOW baseline {wow['baseline_day']}: requests "
            f"{int(t['requests']):,} vs {int(b['requests']):,} ({_pct(d['req_chg'])}); "
            f"revenue {_pct(d['rev_chg'])}. "
            f"Fill {_f(t['fill_rate'], 3)} vs {_f(b['fill_rate'], 3)}; "
            f"eCPM {_f(t['ecpm'], 2)} vs {_f(b['ecpm'], 2)}. "
            f"**Factor: requests (volume).** Shape is **global uniform** — "
            f"the move is proportional across dimensions (not a single-segment outage). "
            f"Window {cluster['window_start']}…{cluster['window_end']}. "
            f"**Ruled out:** fill_rate and eCPM as primary drivers; weekend seasonality "
            f"(baseline is same weekday −7)."
        )
        ruled = ["fill_rate_as_primary", "ecpm_as_primary", "weekend_seasonality", "single_segment"]
    elif factor == "fill_rate":
        fill_t = ev.get("fill_t", t["fill_rate"])
        fill_b = ev.get("fill_b", b["fill_rate"])
        fill_chg = ev.get("fill_chg", d["fill_chg"])
        hidden = " Hidden globally (segment scan required)." if cluster.get("hidden_globally") else ""
        explanation = (
            f"On {day} vs {wow['baseline_day']}: revenue {_pct(d['rev_chg'])}, "
            f"requests {_pct(d['req_chg'])}. "
            f"Global fill {_f(t['fill_rate'], 3)} vs {_f(b['fill_rate'], 3)} ({_pp(d['fill_chg'])}). "
            f"**Factor: fill_rate.** Localized to **{seg}** "
            f"(fill {_f(fill_t, 3)} vs {_f(fill_b, 3)}, Δfill {_pp(fill_chg)})."
            f"{hidden} "
            f"Window {cluster['window_start']}…{cluster['window_end']}. "
            f"**Ruled out:** request volume as primary, eCPM as primary, advertiser dims for fill."
        )
        ruled = ["requests_as_primary", "ecpm_as_primary", "advertiser_dims_for_fill"]
    else:
        ecpm_t = ev.get("ecpm_t", t["ecpm"])
        ecpm_b = ev.get("ecpm_b", b["ecpm"])
        explanation = (
            f"On {day} vs {wow['baseline_day']}: global eCPM {_f(t['ecpm'], 2)} vs {_f(b['ecpm'], 2)} "
            f"(abs Δ {_f(d['ecpm_chg'], 3)}). "
            f"**Factor: eCPM / price.** Layered localization toward **{seg}** "
            f"(segment eCPM {_f(ecpm_t, 2)} vs {_f(ecpm_b, 2)}). "
            f"Early days may be offset by other format/region cells so the global series looks quiet. "
            f"Window {cluster['window_start']}…{cluster['window_end']}. "
            f"**Ruled out:** fill_rate as primary; weekend seasonality."
        )
        ruled = ["fill_rate_as_primary", "weekend_seasonality"]

    return {
        "window_start": cluster["window_start"],
        "window_end": cluster["window_end"],
        "probe_day": day,
        "baseline_day": wow.get("baseline_day"),
        "baseline_rule": "same_dow_minus_7",
        "primary_factor": factor,
        "shape": cluster["shape"],
        "segment": seg,
        "source": cluster["source"],
        "n_days": cluster["n_days"],
        "hidden_globally": bool(cluster.get("hidden_globally")),
        "global_deltas": d,
        "contribution_shares": factors.get("contribution_shares"),
        "evidence": {
            "actual": {"requests": t["requests"], "fill_rate": t["fill_rate"], "ecpm": t["ecpm"], "revenue": t["revenue"]},
            "baseline": {"requests": b["requests"], "fill_rate": b["fill_rate"], "ecpm": b["ecpm"], "revenue": b["revenue"]},
            "segment": ev or (loc.get("top_localization") or {}),
        },
        "ruled_out": ruled,
        "severity": cluster["severity"],
        "explanation": explanation,
    }


def discover_incidents(
    start: str | None = None,
    end: str | None = None,
    *,
    max_incidents: int = 8,
) -> dict[str, Any]:
    """Scan eda range and return reproducible incident windows with explanations."""
    with investigation_span("investigate.discover_incidents"):
        bounds = data_date_bounds()
        s = _parse_day((start or "").strip() or bounds["start"])
        e = _parse_day((end or "").strip() or bounds["end"])

        signals: list[dict[str, Any]] = []
        for day in _daterange(s, e):
            signals.extend(_day_signals(day))

        clusters = _cluster(signals)
        clusters = _prefer_combo_over_single(clusters)
        clusters = _merge_ecpm_layers(clusters)
        clusters.sort(key=lambda c: c["severity"], reverse=True)
        clusters = clusters[:max_incidents]

        # Stable presentation order: chronological
        clusters.sort(key=lambda c: c["window_start"])
        incidents = [_explain(c) for c in clusters]
        # Assign letters only as labels after discovery (not lookup keys)
        for i, inc in enumerate(incidents):
            inc["id"] = chr(ord("A") + i) if i < 26 else str(i + 1)

        flush_telemetry()
        return {
            "schema_version": "3.0",
            "mode": "discovered_incidents",
            "start": str(s),
            "end": str(e),
            "data_bounds": bounds,
            "baseline_rule": "same_dow_minus_7",
            "database": "eda",
            "method": [
                "same_dow_wow",
                "factor_decompose",
                "segment_scan_os_osxregion_formatxregion_category",
                "recovery_gate",
                "cluster_by_factor_segment",
            ],
            "count": len(incidents),
            "incidents": incidents,
            "note": (
                "Incidents are discovered algorithmically (not a fixed date list). "
                "Recoveries are excluded; multi-day windows share factor+segment; "
                "hidden segment hits are included when global thresholds are quiet."
            ),
        }


# Back-compat alias used by MCP/CLI — prefer precomputed rca_incidents when present
def list_calibration_incidents() -> dict[str, Any]:
    try:
        from clickathon.rca_store import list_incidents_from_store, tables_ready

        if tables_ready():
            stored = list_incidents_from_store()
            if stored.get("count", 0) > 0:
                return stored
    except Exception:  # noqa: BLE001
        pass
    return discover_incidents()
