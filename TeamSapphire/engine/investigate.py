"""The investigation loop — ties the deterministic stages into one pass.

    detect (global)  +  detect (per segment)
            |
            v
    consolidate overlapping incidents into distinct EVENTS
            |
            v
    for each event:  decompose  ->  localize  ->  ruled-out ledger
            |
            v
    structured diagnosis  (the narrator reads this, and only this)

WHY CONSOLIDATION IS ITS OWN STEP
---------------------------------
The scans return incidents, not events, and one real event produces a great many
incidents. On 2026-06-21 a single platform-wide traffic loss surfaced as 2 global
incidents plus 225 segment ones — every dimension value dropped ~45%, so every
one of them tripped independently. Reporting 227 findings for one event would be
noise dressed as thoroughness, and a reader could not tell how many
things actually went wrong.

Overlapping incidents are therefore merged into a single event, and the
localizer decides what kind of event it was: if one segment carries the movement
beyond what its size explains it is localized, and if every segment moved
together it is global. That distinction is the whole diagnosis — "everything
dropped" and "one thing broke" are different incidents with different owners.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any

from .db import DB, QueryLog
from .detect import (
    Incident, cluster_incidents, detect, detect_segments,
)
from .characterize import characterize
from .decompose import Decomposition, decompose
from .intersect import scan_intersections
from .localize import DimensionVerdict, localize
from .trace import NullTracer

# Incidents whose windows overlap, or sit within this gap, are one event.
EVENT_MERGE_GAP_HOURS = 6

# Event severity is "percent-hours": how far off, for how long, on the strongest
# signal that triggered it. Measured on the training window this separates real
# events from blips by more than an order of magnitude —
#   2026-06-21 global traffic loss   0.455 x 24h = 10.9
#   Android 15 fill failure          0.448 x 72h = 32.3
#   typical 3-hour wobble            0.05  x  3h =  0.15
# so a floor of 1.0 keeps both real events and drops the noise.
MIN_EVENT_SEVERITY = 1.0


@dataclass
class Event:
    start: str
    end: str
    hours: int
    classification: str           # "localized" | "global" | "unattributed"
    severity: float               # percent-hours of the strongest trigger
    headline: str
    primary_factor: str
    revenue_pct_change: float
    trigger_count: int
    triggers: list[dict]
    decomposition: dict
    responsible: list[dict]
    ruled_out: list[dict]
    # Shape of the transition — the step between "which segment" and "why".
    signature: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Investigation:
    window_start: str
    window_end: str
    trace_url: str | None = None
    events: list[Event] = field(default_factory=list)
    detector_ledger: list[dict] = field(default_factory=list)
    discarded_noise: int = 0
    suppressed_low_severity: int = 0
    # Compound anomalies: cells that moved substantially more than either parent
    # dimension, so no single-dimension scan can see them by construction.
    compound_findings: list[dict] = field(default_factory=list)
    compound_ledger: list[dict] = field(default_factory=list)
    total_query_ms: float = 0.0
    total_rows_read: int = 0
    queries: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["events"] = [e.to_dict() for e in self.events]
        return d


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(str(s))


def _merge_incidents(incidents: list[Incident]) -> list[list[Incident]]:
    """Group incidents around the strongest signal in each cluster.

    Sweeping left to right and extending a horizon as each incident joins looks
    natural and is wrong: it merges transitively. A chain of individually
    overlapping incidents links events that have nothing to do with each other,
    and the first run did exactly that — 206 incidents spanning 278 hours were
    reported as one event, swallowing both a global traffic loss on 06-21 and an
    unrelated Android 15 fill failure two days later.

    Instead the strongest incident seeds an event and claims only what overlaps
    *it*. The seed's window never grows, so nothing can chain, and the event's
    window stays the one belonging to its dominant signal.
    """
    remaining = sorted(incidents, key=lambda i: abs(i.mean_pct_change) * i.hours, reverse=True)
    groups: list[list[Incident]] = []
    gap = timedelta(hours=EVENT_MERGE_GAP_HOURS)

    while remaining:
        seed = remaining.pop(0)
        seed_start, seed_end = _parse(seed.start_hour), _parse(seed.end_hour)
        group, rest = [seed], []
        for inc in remaining:
            if _parse(inc.start_hour) <= seed_end + gap and _parse(inc.end_hour) >= seed_start - gap:
                group.append(inc)
            else:
                rest.append(inc)
        remaining = rest
        groups.append(group)
    return groups


def usable_baseline_weeks(db: DB, start: str, requested: int) -> int:
    """How many weeks of baseline actually exist behind `start`.

    A shifted baseline window that reaches past the beginning of the data comes
    back partially covered rather than empty, so a "requests > 0" check passes
    while the totals are only a fraction of a real window. The baseline then
    reads far too low and the target window looks like a spike — which is how a
    44% drop was first reported as +18.5% revenue growth.

    Clamping to whole weeks that fit entirely inside the data makes every
    comparison a like-for-like one.
    """
    row = db.query(
        "SELECT min(hour) AS first_hour FROM inmobi.events_hourly",
        label="baseline:data_range",
    ).first()
    if not row or row["first_hour"] is None:
        return requested
    available = (_parse(start) - _parse(row["first_hour"])).total_seconds() / 3600.0
    return max(1, min(requested, int(available // (24 * 7))))


def _headline(cls: str, factor: str, dec: Decomposition,
              responsible: list[DimensionVerdict]) -> str:
    move = f"{dec.revenue_pct_change:+.1%}"
    if cls == "localized":
        top = responsible[0]
        seg = top.segments[0]
        factor_move = next((f.pct_change for f in dec.factors if f.factor == factor), 0.0)
        return (f"Revenue {move}, driven by {factor} in "
                f"{top.dim_name}={top.top_value} "
                f"({seg.pct_change:+.1%} vs {factor_move:+.1%} across the platform)")
    if cls == "global":
        return (f"Revenue {move}, driven by {factor} falling uniformly across "
                f"every dimension — no single segment responsible")
    return f"Revenue {move}, driven by {factor}; no dimension met the attribution bar"


def investigate(
    db: DB,
    start: str,
    end: str,
    weeks: int = 4,
    scan_segments: bool = True,
    scan_compounds: bool = True,
    tracer=None,
) -> Investigation:
    """Run the full deterministic investigation over [start, end)."""
    tracer = tracer or NullTracer()
    inv = Investigation(window_start=start, window_end=end,
                        trace_url=getattr(tracer, "trace_url", None))

    with tracer.span("detect:global", window=[start, end], baseline_weeks=weeks):
        global_findings, global_checked = detect(db, start, end, weeks=weeks)
        inv.detector_ledger.extend([{**c, "scan": "global"} for c in global_checked])
        tracer.update(output={"metrics_checked": global_checked,
                              "hours_flagged": len(global_findings)})

    all_findings = list(global_findings)
    if scan_segments:
        with tracer.span("detect:segments", window=[start, end], baseline_weeks=weeks):
            seg_findings, seg_checked = detect_segments(db, start, end, weeks=weeks)
            inv.detector_ledger.extend(seg_checked)
            all_findings.extend(seg_findings)
            tracer.update(output={"metrics_checked": seg_checked,
                                  "segment_hours_flagged": len(seg_findings)})

    with tracer.span("consolidate", raw_findings=len(all_findings)):
        incidents, discarded = cluster_incidents(all_findings)
        inv.discarded_noise = len(discarded)
        tracer.update(output={
            "incidents": len(incidents),
            "discarded_as_noise": len(discarded),
            "why": "isolated flagged hours are noise; a sustained run is an event",
        })

    for group in _merge_incidents(incidents):
        # The seed (first, strongest) defines the window; joiners do not stretch it.
        seed = group[0]
        ev_start, ev_end = seed.start_hour, seed.end_hour

        ev_weeks = usable_baseline_weeks(db, ev_start, weeks)

        with tracer.span(f"event {ev_start} .. {ev_end}",
                         triggers=len(group), seed=seed.scope):
            with tracer.span("decompose", window=[ev_start, ev_end]):
                dec = decompose(db, ev_start, ev_end, weeks=ev_weeks)
                tracer.update(output={
                    "revenue_pct_change": round(dec.revenue_pct_change, 4),
                    "primary_factor": dec.primary_factor,
                    "identity_residual": dec.identity_residual,
                    "factors": [{"factor": f.factor,
                                 "pct_change": round(f.pct_change, 4),
                                 "share_of_move": round(f.contribution_share, 4)}
                                for f in dec.factors],
                })

            with tracer.span("localize", factor=dec.primary_factor):
                responsible, ruled_out = localize(
                    db, ev_start, ev_end, dec.primary_factor, weeks=ev_weeks)
                tracer.update(output={
                    "responsible": [v.summary() for v in responsible],
                    # Ruled-out branches are evidence, not omissions.
                    "ruled_out": [v.summary() for v in ruled_out],
                })

            # Shape of the transition. Naming the factor and segment is a
            # sharper "what"; how the change arrived is where the "why" is.
            # Scoped to the responsible segment when there is one, so we
            # characterise the thing that actually moved rather than its
            # diluted platform-wide shadow.
            top = responsible[0] if responsible else None
            with tracer.span("characterize", factor=dec.primary_factor,
                             scope=f"{top.dim_name}={top.top_value}" if top else "global"):
                try:
                    sig = characterize(
                        db, ev_start, ev_end, dec.primary_factor,
                        dim_name=top.dim_name if top else None,
                        dim_value=top.top_value if top else None,
                    )
                    signature = sig.to_dict()
                    tracer.update(output=signature)
                except Exception as exc:  # noqa: BLE001 — never sink the run
                    signature = None
                    tracer.update(output={"error": str(exc)})

        if responsible:
            classification = "localized"
        elif all(v.verdict == "uniform" for v in ruled_out):
            classification = "global"
        else:
            classification = "unattributed"

        # Triggers are ranked so the narrator sees the strongest signal first,
        # and capped because one event can raise hundreds of near-identical ones.
        triggers = sorted(group, key=lambda i: abs(i.mean_pct_change) * i.hours, reverse=True)

        severity = abs(seed.mean_pct_change) * seed.hours
        if severity < MIN_EVENT_SEVERITY:
            inv.suppressed_low_severity += 1
            continue

        inv.events.append(Event(
            start=ev_start,
            end=ev_end,
            severity=round(severity, 2),
            hours=int((_parse(ev_end) - _parse(ev_start)).total_seconds() // 3600) + 1,
            classification=classification,
            headline=_headline(classification, dec.primary_factor, dec, responsible),
            primary_factor=dec.primary_factor,
            revenue_pct_change=dec.revenue_pct_change,
            trigger_count=len(group),
            triggers=[{
                "scope": i.scope, "metric": i.metric, "direction": i.direction,
                "hours": i.hours, "mean_pct_change": round(i.mean_pct_change, 4),
                "peak_z": round(i.peak_z, 2),
            } for i in triggers[:8]],
            decomposition=dec.to_dict(),
            responsible=[v.to_dict() for v in responsible],
            ruled_out=[v.summary() for v in ruled_out],
            signature=signature,
        ))

    # Compound scan runs last so it can suppress findings already explained by
    # a single-dimension event — a strong single cause casts a shadow across
    # every pair correlated with it.
    if scan_compounds:
        with tracer.span("detect:compound"):
            try:
                # Only windows with an ESTABLISHED single-dimension cause cast a
                # shadow worth suppressing. An "unattributed" event is precisely
                # one we could not explain — suppressing compounds there would
                # discard the explanation. Measured: the 06-28..30 iOS/APAC
                # compound was suppressed by its own unattributed event until
                # this distinction was made.
                known = [(e.start, e.end) for e in inv.events
                         if e.classification in ("localized", "global")]
                compounds, ledger = scan_intersections(
                    db, start, end, metric="fill_rate", weeks=weeks,
                    known_windows=known)
                inv.compound_findings = [c.to_dict() for c in compounds]
                inv.compound_ledger = ledger
                tracer.update(output={
                    "novel_compound_findings": len(compounds),
                    "top": [{"day": c.day, "scope": c.scope,
                             "pct_change": round(c.pct_change, 4),
                             "parent_a_pct": round(c.parent_a_pct, 4),
                             "parent_b_pct": round(c.parent_b_pct, 4)}
                            for c in compounds[:5]],
                })
            except Exception as exc:  # noqa: BLE001
                tracer.update(output={"error": str(exc)})

    inv.events.sort(key=lambda e: e.severity, reverse=True)
    tracer.update(output={
        "events": [{"window": [e.start, e.end], "classification": e.classification,
                    "headline": e.headline, "severity": e.severity} for e in inv.events],
        "total_query_ms": db.log.total_ms,
        "total_rows_read": db.log.total_rows_read,
    })
    inv.total_query_ms = db.log.total_ms
    inv.total_rows_read = db.log.total_rows_read
    inv.queries = db.log.as_evidence()
    return inv
