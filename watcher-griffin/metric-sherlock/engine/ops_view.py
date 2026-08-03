"""The operations view: what an ad-ops reader needs, assembled with NO input.

WHY THIS MODULE EXISTS
----------------------
The old UI asked the operator to pick a metric and type two timestamps before it
would show anything. That requires them to already know what moved and when --
which is precisely the manual dashboard-drilling the problem statement says takes
hours or days. So no function here takes a metric, a window, or a dimension.

"Now" is the DATA's clock, not the wall clock: max(event_time), or
SCANNER_AS_OF_OVERRIDE when pinned to a static dataset. That single decision is what
removes every date picker.

THE METRIC TREE
---------------
Built from the revenue identity in Docs/metrics_glossary.md, which is exact:

    Revenue = Requests x Fill rate x Show rate x eCPM / 1000

with CTR carried alongside as an engagement signal rather than a factor (it does
not multiply into revenue in a CPM model).

The tree is the answer to "show only what affects it". The operator does not choose
a metric -- the tree colours every node from its own band and marks the one carrying
the largest share of the revenue move as the DRIVER. Selection is done by the
arithmetic, not by the human.

Node status is a real band verdict, not a heuristic on a z-score. It comes from the
same engine/bands.evaluate() the detector uses, so a node cannot be green here while
the monitor considers it breached.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from engine.ch_client import Trace, get_client
from engine.config import METRIC_DEFS, REVENUE_DECOMPOSITION_FACTORS, settings, utc_now
from engine.grains import GRAIN_REGISTRY, grain, monitored_grains
from engine.scopes import scope

# The tree, in funnel order. `revenue` is the root; the four factors multiply into
# it exactly; ctr hangs off the side.
TREE_ROOT = "revenue"
TREE_FACTORS = list(REVENUE_DECOMPOSITION_FACTORS)   # requests, fill_rate, render_rate, ecpm
TREE_SIBLINGS = ["ctr"]
TREE_METRICS = [TREE_ROOT] + TREE_FACTORS + TREE_SIBLINGS

# The grain the tree is displayed at. Daily is the grain an ops conversation
# actually happens in ("yesterday was down"), and on this dataset it is comfortably
# above every metric's power floor at global scope. The per-grain ladder beside each
# node is what exposes the other 13, so nothing is hidden by this choice.
DEFAULT_TREE_GRAIN = "1d"

# How many historical points each band chart shows.
SPARKLINE_POINTS = 21


@dataclass
class TreeNode:
    metric: str
    label: str
    role: str                 # 'root' | 'factor' | 'sibling'
    owner: str
    status: str = "unknown"   # 'good' | 'amber' | 'red' | 'not_judgeable'
    value: Optional[float] = None
    center: Optional[float] = None
    spread: Optional[float] = None
    deviation_score: Optional[float] = None
    pct_change: Optional[float] = None
    direction: str = "none"
    is_driver: bool = False
    share_of_move: Optional[float] = None   # signed log-share of the revenue move
    unit: str = ""
    reason: str = ""
    seasonal_cell: str = ""
    sample_count: int = 0
    baseline_method: str = ""
    series: list = field(default_factory=list)
    grain_ladder: list = field(default_factory=list)
    source_step: str = ""

    def as_dict(self) -> dict:
        return {
            "metric": self.metric, "label": self.label, "role": self.role, "owner": self.owner,
            "status": self.status, "value": self.value, "center": self.center,
            "spread": self.spread, "deviation_score": self.deviation_score,
            "pct_change": self.pct_change, "direction": self.direction,
            "is_driver": self.is_driver, "share_of_move": self.share_of_move,
            "unit": self.unit, "reason": self.reason, "seasonal_cell": self.seasonal_cell,
            "sample_count": self.sample_count, "baseline_method": self.baseline_method,
            "series": self.series, "grain_ladder": self.grain_ladder,
            "source_step": self.source_step,
        }


# Human labels and units. The old UI rendered raw identifiers -- `fill_rate`,
# `ecpm`, `rpr`, `z=` -- to an audience that has no reason to know them.
METRIC_LABELS = {
    "revenue": ("Revenue", "$"),
    "requests": ("Ad requests", ""),
    "fills": ("Fills", ""),
    "impressions": ("Impressions", ""),
    "clicks": ("Clicks", ""),
    "fill_rate": ("Fill rate", "%"),
    "render_rate": ("Show rate", "%"),
    "ctr": ("Click-through rate", "%"),
    "ecpm": ("eCPM", "$"),
    "rpr": ("Revenue per request", "$"),
}

# What a breach of each metric means in business terms, and who acts on it. Shown
# next to the node so the reader does not have to know the funnel by heart.
METRIC_MEANING = {
    "revenue": "money earned on rendered impressions",
    "requests": "ad opportunities arriving -- traffic, not monetisation",
    "fill_rate": "share of requests an advertiser answered; falls when demand dries up",
    "render_rate": "share of bought ads actually shown; falls on render or player faults",
    "ecpm": "price per thousand impressions; falls on cheaper demand mix",
    "ctr": "engagement with shown ads; leads CPC and CPI revenue",
}


def data_clock(client=None, trace: Optional[Trace] = None,
               explicit: Optional[datetime] = None) -> dict:
    """The system's notion of 'now', and why. Replaces every date picker.

    Resolution order, and the reason for each rung:

      1. an explicit `as_of` -- honoured exactly. Callers that sweep a specific
         historical window (the backtest, a demo of a known incident) need
         determinism, so this is never clamped.
      2. SCANNER_AS_OF_OVERRIDE -- an operator deliberately pinning the clock.
      3. otherwise min(wall clock, max(event_time)) -- CLAMPED.

    Rung 3 is the fix for a real defect. `SCANNER_AS_OF_OVERRIDE` is not set in
    utils/.env, so the deployed scanner was resolving "now" to the real wall clock
    (August 2026) against a dataset that ends 2026-07-05 -- every tick evaluated a
    window containing no data whatsoever and found nothing, silently. It looked like
    a quiet system rather than a misconfigured one.
    """
    client = client or get_client()
    trace = trace if trace is not None else Trace()
    rows = client.query(
        "SELECT max(event_time) AS max_event_time, count() AS total_rows FROM ad_events",
        step="ops:data_clock", trace=trace,
    )
    row = rows[0] if rows else {"max_event_time": None, "total_rows": 0}
    latest = row["max_event_time"]
    pinned = settings.scanner_as_of_override
    wall = utc_now()

    if explicit is not None:
        as_of, source = explicit, "explicit"
        explanation = (
            f"'Now' was supplied explicitly as {explicit:%Y-%m-%d %H:%M} -- used exactly as "
            f"given, not clamped, so a specific window can be reproduced."
        )
    elif pinned is not None:
        as_of, source = pinned, "pinned"
        explanation = (
            "'Now' is pinned by SCANNER_AS_OF_OVERRIDE because this dataset is static; "
            "with live timestamps it follows the latest event instead."
        )
    elif latest is not None and wall > latest:
        # Clamped. Preferred over requiring the env var to be set correctly, because it
        # also works unchanged for the unseen-incident dataset whatever its date range.
        as_of, source = latest, "clamped"
        behind_days = (wall - latest).days
        explanation = (
            f"'Now' follows the latest event in the data ({latest:%Y-%m-%d %H:%M}). The real "
            f"clock is {behind_days} day(s) further ahead, so it was clamped -- evaluating a "
            f"window past the end of the data would report silence rather than health."
        )
    else:
        as_of, source = latest or wall, "live"
        explanation = "'Now' follows the latest event in the data, so the view never asks for a date."

    return {
        "as_of": as_of,
        "max_event_time": latest,
        "total_rows": int(row["total_rows"] or 0),
        "pinned": pinned is not None,
        "source": source,
        "clamped": source == "clamped",
        "explanation": explanation,
        "source_step": "ops:data_clock",
    }


def resolve_as_of(explicit: Optional[datetime] = None, client=None,
                  trace: Optional[Trace] = None) -> datetime:
    """Just the timestamp, for callers that do not need the whole clock block.

    One definition, shared by the console and the scanner, so the two can never
    disagree about what "now" means -- which they did: the console fell back to
    max(event_time) while the scanner fell back to the wall clock.
    """
    return data_clock(client=client, trace=trace, explicit=explicit)["as_of"]


def _status_for(verdict) -> str:
    if verdict is None:
        return "not_judgeable"
    if verdict.skipped:
        return "not_judgeable"
    if verdict.severity == "red":
        return "red"
    if verdict.severity == "amber":
        return "amber"
    return "good"


def metric_tree(as_of: datetime, trace: Trace, client=None,
                grain_name: str = DEFAULT_TREE_GRAIN,
                sparkline_points: int = SPARKLINE_POINTS) -> dict:
    """The colour-coded funnel, plus each node's history and grain ladder."""
    from engine.sweep import band_series, sweep_pair

    g = grain(grain_name)
    s = scope("global")
    client = client or get_client()

    # Every evaluated verdict, including the ones inside their band -- a tree that
    # can only show red cannot show that the rest of the funnel is fine.
    collected: list = []
    sweep_pair(s, g, as_of, TREE_METRICS, trace, collect=collected)
    by_metric = {v.metric: v for v in collected}

    series = band_series(s, g, as_of, TREE_METRICS, trace,
                        points=sparkline_points, client=client)
    ladders = grain_ladder(as_of, trace, client=client, metrics=TREE_METRICS)

    nodes = []
    for metric in TREE_METRICS:
        v = by_metric.get(metric)
        label, unit = METRIC_LABELS.get(metric, (metric, ""))
        role = ("root" if metric == TREE_ROOT
                else "factor" if metric in TREE_FACTORS else "sibling")
        node = TreeNode(
            metric=metric, label=label, role=role,
            owner=METRIC_DEFS[metric].owner, unit=unit,
            status=_status_for(v),
            grain_ladder=ladders.get(metric, []),
            series=series.get(metric, []),
            source_step=f"sweep:global:{grain_name}:windows",
        )
        if v is not None:
            node.value = v.value
            node.center = v.center if not v.skipped else None
            node.spread = v.spread if not v.skipped else None
            node.deviation_score = v.deviation_score if not v.skipped else None
            node.pct_change = v.pct_change
            node.direction = v.direction
            node.seasonal_cell = v.seasonal_cell
            node.sample_count = v.sample_count
            node.baseline_method = v.method
            node.reason = v.as_reason()
        else:
            node.reason = (
                f"{label} was not evaluated at the {grain_name} grain in this window, so no "
                f"status can be claimed for it"
            )
        nodes.append(node)

    _mark_driver(nodes)
    return {
        "grain": grain_name,
        "grain_seconds": g.seconds,
        "window_start": g.window_for(as_of)[0],
        "window_end": g.window_for(as_of)[1],
        "identity": "Revenue = Requests x Fill rate x Show rate x eCPM / 1000",
        "identity_note": (
            "This identity is exact -- every intermediate term cancels -- so the factor shares "
            "below account for the revenue move with no residual."
        ),
        "nodes": [n.as_dict() for n in nodes],
        "meanings": METRIC_MEANING,
    }


def _mark_driver(nodes: list) -> None:
    """Marks the factor carrying the largest share of the revenue move.

    This is the 'select only what affects it' step. Shares are computed in log space
    from each factor's own value-vs-centre ratio, normalised by the sum of absolute
    log ratios -- the same construction engine/decompose.py uses, so the tree and the
    investigation cannot disagree about which factor is responsible.

    Only FACTORS are eligible. Revenue is the thing being explained, and CTR is not a
    factor of it, so neither can be the driver.
    """
    import math

    factors = [n for n in nodes if n.role == "factor"]
    logs = {}
    for n in factors:
        if n.value is None or n.center is None or n.value <= 0 or n.center <= 0:
            logs[n.metric] = 0.0
        else:
            logs[n.metric] = math.log(n.value / n.center)
    total_abs = sum(abs(v) for v in logs.values())
    for n in factors:
        n.share_of_move = (logs[n.metric] / total_abs) if total_abs else 0.0

    # The driver must itself be out of band. A factor holding the largest share of a
    # tiny, entirely-within-band wobble is not driving anything, and labelling it
    # "driver" would manufacture a cause for a non-event.
    breached = [n for n in factors if n.status in ("amber", "red")]
    pool = breached or []
    if pool:
        max(pool, key=lambda n: abs(n.share_of_move or 0.0)).is_driver = True


def grain_ladder(as_of: datetime, trace: Trace, client=None,
                 metrics: Optional[list] = None, scope_name: str = "global") -> dict:
    """Status of each metric at EVERY monitored grain: {metric: [{grain, status, ...}]}.

    This is how "all time frames were considered" becomes visible rather than
    asserted, and it is diagnostically useful on its own: the same drop shows as red
    at 5m and green at 3w if it is a blip, and the reverse if it is slow erosion.

    Four states, deliberately. Collapsing 'within band' and 'no valid band' into one
    green would turn an admitted gap -- the 1mo grain has no usable baseline on a
    35-day dataset, and per-app CTR has none at any grain -- into a false all-clear.
    """
    from engine.sweep import sweep_pair

    from concurrent.futures import ThreadPoolExecutor

    from engine.tracing import in_parent_context

    metrics = metrics or TREE_METRICS
    s = scope(scope_name)
    grain_names = monitored_grains()

    def evaluate_grain(gn: str) -> tuple:
        g = GRAIN_REGISTRY[gn]
        if not s.supports(g):
            return gn, None, (
                f"{s.label} has no source table at the {gn} grain -- sub-hour rollups exist "
                f"only for overall, region and ad format"
            )
        collected: list = []
        try:
            sweep_pair(s, g, as_of, metrics, trace, collect=collected)
        except Exception as e:
            return gn, None, f"evaluation failed at {gn}: {e}"
        return gn, {v.metric: v for v in collected}, None

    # Concurrent, because 14 grains x 2 queries run serially is ~3.5s of pure
    # round-trip latency on a screen that polls every 30 seconds -- and the grains
    # are entirely independent of each other. in_parent_context is applied on THIS
    # thread so the workers inherit the OTel context; without it every query span
    # orphans into its own root trace (PROGRESS.md gotcha #13).
    worker = in_parent_context(evaluate_grain)
    with ThreadPoolExecutor(max_workers=min(8, len(grain_names))) as pool:
        results = list(pool.map(worker, grain_names))

    out = {m: [] for m in metrics}
    order = {gn: i for i, gn in enumerate(grain_names)}
    for gn, seen, err in sorted(results, key=lambda r: order[r[0]]):
        for m in metrics:
            if seen is None:
                out[m].append({"grain": gn, "status": "not_judgeable", "reason": err})
                continue
            v = seen.get(m)
            out[m].append({
                "grain": gn,
                "status": _status_for(v),
                "deviation_score": (v.deviation_score if v is not None and not v.skipped else None),
                "value": v.value if v is not None else None,
                "center": (v.center if v is not None and not v.skipped else None),
                "sample_count": v.sample_count if v is not None else 0,
                "reason": (v.as_reason() if v is not None else
                           f"{m} was not evaluated at the {gn} grain"),
            })
    return out


def ops_summary(as_of: Optional[datetime] = None, incident_limit: int = 25) -> dict:
    """Everything the operations home screen needs, in one call, with no parameters.

    Deliberately one round trip: the alternative is a screen that renders in four
    stages and shows a different total in each.
    """
    from engine import monitor_store

    trace = Trace()
    client = get_client()
    clock = data_clock(client, trace, explicit=as_of)
    as_of = clock["as_of"]

    tree = metric_tree(as_of, trace, client=client)
    # Fetched as two pages, not one. The list is ordered by time and the suppressed rows
    # outnumber the raised ones 791 to 34, so a single chronological page of 25 came back
    # nine-tenths gated -- the queue said "top 9 of 34" while 25 rows were available.
    alertable = monitor_store.list_incidents(limit=incident_limit, gated=False)
    incidents = alertable + monitor_store.list_incidents(limit=incident_limit, gated=True)
    # Counted over the whole table rather than over the page above: `incidents` is capped at
    # incident_limit, so deriving the suppressed count from it reported 0 whenever the page
    # was full of alertable rows. See monitor_store.count_incidents.
    totals = monitor_store.count_incidents()

    # Both of these are aggregated in SQL over the WHOLE table, never over `alertable` -- which
    # is a page of `incident_limit` rows. That mattered even when the page was the costliest 25
    # (the total was quietly short, and the owner chips summed to 25 beside a headline of 34);
    # now that the list is ordered by time, a page is the 25 most recent and is not a population
    # at all. Same reasoning as count_incidents' own docstring.
    #
    # at_risk stays a DAILY RATE and stays loss-direction only: raw window figures are not
    # addable across grains, and netting above-band moves against shortfalls would understate
    # the exposure. It is still an over-estimate where two incidents describe overlapping
    # traffic, which is why it is labelled an estimate rather than an accounting total -- and
    # why it is no longer the headline.
    at_risk = float(totals.get("at_risk_usd_per_day") or 0.0)
    by_owner = monitor_store.count_incidents_by_owner()

    # The headline: the largest movement currently outside its band. One metric, one segment,
    # how far it went -- the thing the detector actually finds.
    peak = monitor_store.peak_movement(as_of=as_of)

    sweep = monitor_store.latest_sweep()

    # The tree is computed live at the data's clock; the incident queue is whatever the
    # monitor last wrote. Those can be different moments, and when they are, the screen
    # would otherwise show an all-green funnel next to a large "revenue at risk" figure
    # with nothing explaining the contradiction. Surface the gap instead of letting the
    # reader discover it.
    staleness = {"stale": False, "reason": ""}
    if sweep and sweep.get("as_of"):
        lag_s = (as_of - sweep["as_of"]).total_seconds()
        # One day: past that, the funnel and the queue are describing different days.
        if lag_s > 86400:
            staleness = {
                "stale": True,
                "sweep_as_of": sweep["as_of"],
                "clock_as_of": as_of,
                "lag_hours": round(lag_s / 3600, 1),
                "reason": (
                    f"The funnel above is evaluated at {as_of:%Y-%m-%d %H:%M}, but the monitor last "
                    f"swept {round(lag_s / 3600)}h earlier at {sweep['as_of']:%Y-%m-%d %H:%M}. The "
                    f"incidents listed are from that earlier sweep, so a healthy funnel here does "
                    f"not mean those incidents are resolved -- it means they have not been "
                    f"re-evaluated. Run the monitor to bring them into agreement."
                ),
            }

    return {
        "clock": clock,
        "tree": tree,
        "staleness": staleness,
        "revenue_at_risk_usd": at_risk,
        "impact_gate_usd": settings.impact_usd_gate,
        # The largest movement outside its band right now: {root_metric, root_scope_type,
        # root_scope_value, grain, direction, root_deviation_score, root_value, root_center,
        # root_severity, incident_id}. Empty dict when nothing is breaching.
        "peak_movement": peak,
        "incidents_open": totals["alertable"],
        "incidents_gated": totals["gated"],
        # How many of the alertable ones this payload actually carries, so the UI can say
        # "showing 25 of 41" instead of implying the list is complete.
        "incidents_returned": len(alertable),
        "incidents_by_owner": by_owner,
        "incidents": incidents,
        "last_sweep": sweep,
        "queries": [
            {"step": e.step, "sql": e.sql, "row_count": e.row_count, "latency_ms": e.latency_ms,
             "error": e.error, "read_rows": e.read_rows, "read_bytes": e.read_bytes}
            for e in trace.entries
        ],
    }
