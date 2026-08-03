"""Precomputed PNG charts for LibreChat (matplotlib Agg). Numbers from rca_* only."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Literal

from clickathon.ch import query_rows
from clickathon.rca_store import counterfactual_from_store, list_incidents_from_store

ChartKind = Literal["window", "factors", "counterfactual"]
CHART_KINDS: tuple[ChartKind, ...] = ("window", "factors", "counterfactual")

REPO_ROOT = Path(__file__).resolve().parents[2]

_plt = None


def _pyplot():
    """Lazy-import matplotlib so serving cached PNGs stays fast."""
    global _plt
    if _plt is None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _plt = plt
    return _plt


def charts_dir() -> Path:
    raw = os.environ.get("CLICKATHON_CHARTS_DIR", "").strip()
    if raw:
        return Path(raw)
    # MCP container layout uses /app; otherwise write next to compose files.
    if Path("/app/src").is_dir():
        return Path("/app/charts")
    return REPO_ROOT / "stack" / "charts"


def charts_public_base() -> str:
    return os.environ.get("CLICKATHON_CHARTS_PUBLIC_BASE", "http://localhost:8001/charts").rstrip("/")


def chart_filename(incident_id: str, kind: ChartKind) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(incident_id).strip()) or "X"
    return f"{safe}_{kind}.png"


def chart_path(incident_id: str, kind: ChartKind) -> Path:
    return charts_dir() / chart_filename(incident_id, kind)


def chart_url(incident_id: str, kind: ChartKind) -> str:
    return f"{charts_public_base()}/{chart_filename(incident_id, kind)}"


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _metric_keys(primary: str) -> tuple[str, str, str]:
    p = (primary or "revenue").lower()
    if p in ("requests", "volume"):
        return "requests", "base_requests", "Requests"
    if p in ("fill_rate", "fill"):
        return "fill_rate", "base_fill_rate", "Fill rate"
    if p == "ecpm":
        return "ecpm", "base_ecpm", "eCPM"
    return "revenue", "base_revenue", "Revenue"


def _window_days(window_start: str, window_end: str) -> list[dict[str, Any]]:
    rows = query_rows(
        """
        SELECT
          event_date,
          requests, base_requests,
          fill_rate, base_fill_rate,
          ecpm, base_ecpm,
          revenue, base_revenue
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
                "day": str(r["event_date"])[:10],
                "requests": r["requests"],
                "base_requests": r["base_requests"],
                "fill_rate": r["fill_rate"],
                "base_fill_rate": r["base_fill_rate"],
                "ecpm": r["ecpm"],
                "base_ecpm": r["base_ecpm"],
                "revenue": r["revenue"],
                "base_revenue": r["base_revenue"],
            }
        )
    return out


def _fig_to_png(fig: Any) -> bytes:
    plt = _pyplot()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def plot_window_png(
    *,
    incident_id: str,
    primary_factor: str,
    window_days: list[dict[str, Any]],
    title_extra: str = "",
) -> bytes:
    plt = _pyplot()
    actual_key, base_key, label = _metric_keys(primary_factor)
    day_labels = [str(w.get("day") or "")[-5:] for w in window_days]
    xs = list(range(len(day_labels)))
    actual = [_f(w.get(actual_key)) or 0.0 for w in window_days]
    baseline = [_f(w.get(base_key)) or 0.0 for w in window_days]

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    if xs:
        ax.plot(xs, actual, marker="o", linewidth=2, color="#0B6E4F", label="Actual")
        ax.plot(xs, baseline, marker="s", linewidth=2, color="#6B7280", label="T−7 baseline")
        ax.set_xticks(xs)
        ax.set_xticklabels(day_labels, rotation=30, ha="right")
    ax.set_title(f"Incident {incident_id}: {label} vs T−7{title_extra}")
    ax.set_xlabel("Day")
    ax.set_ylabel(label)
    ax.legend(loc="best", frameon=False)
    ax.grid(True, axis="y", alpha=0.25)
    return _fig_to_png(fig)


def plot_factors_png(
    *,
    incident_id: str,
    shares: dict[str, Any],
) -> bytes:
    plt = _pyplot()
    labels = ["Requests", "Fill rate", "eCPM"]
    keys = ["requests", "fill_rate", "ecpm"]
    vals = [abs(_f(shares.get(k)) or 0.0) for k in keys]
    colors = ["#2563EB", "#0B6E4F", "#B45309"]

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bars = ax.barh(labels, vals, color=colors)
    ax.set_xlabel("|Contribution share|")
    ax.set_title(f"Incident {incident_id}: factor contribution shares")
    ax.set_xlim(0, max(vals + [0.01]) * 1.25)
    ax.grid(True, axis="x", alpha=0.25)
    for bar, v in zip(bars, vals, strict=True):
        ax.text(v + max(vals + [0.01]) * 0.02, bar.get_y() + bar.get_height() / 2, f"{v:.2f}", va="center")
    return _fig_to_png(fig)


def plot_counterfactual_png(*, incident_id: str, cf: dict[str, Any]) -> bytes:
    plt = _pyplot()
    labels = [
        "Actual",
        "If fill @ T−7",
        "If eCPM @ T−7",
        "If requests @ T−7",
    ]
    keys = [
        "revenue_actual",
        "revenue_if_fill_at_baseline",
        "revenue_if_ecpm_at_baseline",
        "revenue_if_requests_at_baseline",
    ]
    vals = [_f(cf.get(k)) or 0.0 for k in keys]
    colors = ["#111827", "#0B6E4F", "#B45309", "#2563EB"]

    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    bars = ax.barh(labels, vals, color=colors)
    ax.set_xlabel("Revenue")
    ax.set_title(f"Incident {incident_id}: counterfactual revenue")
    ax.grid(True, axis="x", alpha=0.25)
    span = max(vals + [1.0])
    for bar, v in zip(bars, vals, strict=True):
        ax.text(v + span * 0.01, bar.get_y() + bar.get_height() / 2, f"{v:,.0f}", va="center", fontsize=8)
    return _fig_to_png(fig)


def render_incident_charts(incident: dict[str, Any]) -> dict[ChartKind, bytes]:
    """Build all three PNGs for one incident dict from list_incidents_from_store."""
    iid = str(incident["id"])
    primary = str(incident.get("primary_factor") or "revenue")
    ws = str(incident.get("window_start") or incident.get("probe_day"))[:10]
    we = str(incident.get("window_end") or incident.get("probe_day"))[:10]
    shares = incident.get("contribution_shares") or {}
    window_days = _window_days(ws, we)
    cf = counterfactual_from_store(incident_id=iid)
    if cf.get("error"):
        cf = {
            "revenue_actual": (incident.get("evidence") or {}).get("actual", {}).get("revenue"),
            "revenue_if_fill_at_baseline": None,
            "revenue_if_ecpm_at_baseline": None,
            "revenue_if_requests_at_baseline": None,
        }
    return {
        "window": plot_window_png(
            incident_id=iid,
            primary_factor=primary,
            window_days=window_days,
            title_extra=f" ({ws}…{we})",
        ),
        "factors": plot_factors_png(incident_id=iid, shares=shares),
        "counterfactual": plot_counterfactual_png(incident_id=iid, cf=cf),
    }


def write_pngs(incident_id: str, pngs: dict[ChartKind, bytes]) -> list[str]:
    out_dir = charts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for kind, data in pngs.items():
        path = chart_path(incident_id, kind)
        path.write_bytes(data)
        written.append(str(path))
    return written


def precompute_all_incident_charts() -> dict[str, Any]:
    """Write PNGs for every row in rca_incidents. Call after materialize."""
    bag = list_incidents_from_store()
    incidents = bag.get("incidents") or []
    written: list[dict[str, str]] = []
    for inc in incidents:
        iid = str(inc["id"])
        pngs = render_incident_charts(inc)
        paths = write_pngs(iid, pngs)
        written.append({"incident_id": iid, "files": ",".join(paths)})
    return {
        "charts_dir": str(charts_dir()),
        "incidents": len(written),
        "incident_ids": [w["incident_id"] for w in written],
        "kinds": list(CHART_KINDS),
        "public_base": charts_public_base(),
    }


def ensure_chart(incident_id: str, kind: ChartKind) -> Path:
    """Return path to PNG, generating on demand if missing."""
    path = chart_path(incident_id, kind)
    if path.is_file() and path.stat().st_size > 0:
        return path
    bag = list_incidents_from_store()
    inc = next((i for i in (bag.get("incidents") or []) if str(i["id"]) == str(incident_id)), None)
    if not inc:
        raise FileNotFoundError(f"incident {incident_id} not in rca_incidents")
    pngs = render_incident_charts(inc)
    write_pngs(str(incident_id), pngs)
    if not path.is_file():
        raise FileNotFoundError(f"failed to write {path}")
    return path


def load_chart_bytes(incident_id: str, kind: ChartKind) -> bytes:
    return ensure_chart(incident_id, kind).read_bytes()


def resolve_kind(chart: str) -> ChartKind:
    c = (chart or "window").strip().lower()
    aliases = {
        "window": "window",
        "series": "window",
        "trend": "window",
        "factors": "factors",
        "factor": "factors",
        "shares": "factors",
        "counterfactual": "counterfactual",
        "cf": "counterfactual",
        "whatif": "counterfactual",
    }
    kind = aliases.get(c)
    if kind is None:
        raise ValueError(f"unknown chart={chart!r}; use window|factors|counterfactual")
    return kind  # type: ignore[return-value]
