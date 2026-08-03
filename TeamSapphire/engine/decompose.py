"""Stage 2 — decomposition.

An incident tells you revenue moved. This stage answers *which factor* moved,
before anyone asks *which segment*. Volume, supply, render and price are four
very different incidents with four different owners, and separating them first
stops the localizer chasing a dimension that was never responsible.

THE IDENTITY
------------
The glossary gives Revenue ~= Requests x Fill rate x eCPM/1000 as a working
approximation. The exact form costs nothing extra and avoids a residual we would
otherwise have to explain away:

    Revenue = Requests x FillRate x RenderRate x (eCPM / 1000)

which is exact by construction, since

    Requests x (Fills/Requests) x (Impressions/Fills) x (Revenue/Impressions)

telescopes to Revenue. Using the exact identity means every cent of the movement
is attributed to a named factor and nothing lands in a fudge term.

WHY LOG SPACE
-------------
The identity is multiplicative, so its changes are additive in logs:

    log(R1/R0) = log(Q1/Q0) + log(F1/F0) + log(RR1/RR0) + log(E1/E0)

Each factor's share of the total log movement is therefore exact and additive,
summing to 100% with no interaction term left over. Attributing multiplicative
change with subtraction instead produces cross-terms that have to be silently
dropped or arbitrarily allocated — which is exactly the sort of quiet fudge that
turns into a number nobody can reproduce.
"""
import math
from dataclasses import dataclass, asdict
from typing import Any

from .db import DB
from .stats import median

FACTORS = ("requests", "fill_rate", "render_rate", "ecpm")


@dataclass
class FactorMove:
    factor: str
    actual: float
    baseline: float
    pct_change: float
    log_change: float
    contribution_share: float   # signed share of the total log movement
    contribution_pct_points: float   # this factor's share expressed on the revenue change

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Decomposition:
    window_start: str
    window_end: str
    baseline_weeks_used: int
    actual: dict[str, float]
    baseline: dict[str, float]
    revenue_pct_change: float
    factors: list[FactorMove]
    primary_factor: str
    identity_residual: float   # must be ~0; proves the decomposition is complete

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["factors"] = [f.to_dict() for f in self.factors]
        return d


def _totals_sql(weeks: int) -> str:
    """Actual window plus the same window shifted back 1..N weeks.

    Shifting the whole contiguous window keeps the comparison exactly
    like-for-like: same weekdays, same hours-of-day, same length.
    """
    parts = [
        """
        SELECT 0 AS weeks_back,
               sum(requests) AS requests, sum(fills) AS fills,
               sum(impressions) AS impressions, sum(clicks) AS clicks,
               sum(revenue) AS revenue
        FROM inmobi.events_hourly
        WHERE hour >= {start:DateTime} AND hour <= {end:DateTime}
        """
    ]
    for k in range(1, weeks + 1):
        parts.append(f"""
        SELECT {k} AS weeks_back,
               sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue)
        FROM inmobi.events_hourly
        WHERE hour >= {{start:DateTime}} - toIntervalWeek({k})
          AND hour <= {{end:DateTime}}   - toIntervalWeek({k})
        """)
    return " UNION ALL ".join(parts) + " ORDER BY weeks_back"


def _metrics_from(t: dict[str, float]) -> dict[str, float]:
    """Derive the four factors from additive totals. All ratios are sum/sum.

    Also passes through the raw funnel counts (fills, impressions, clicks) —
    already summed by the query, not recomputed here. They add nothing to the
    factor decomposition itself, but let a consumer (e.g. the UI's funnel
    chart) render requests -> fills -> impressions -> clicks without ever
    multiplying a rate back out client-side.
    """
    q = float(t["requests"]) or 0.0
    f = float(t["fills"]) or 0.0
    i = float(t["impressions"]) or 0.0
    c = float(t["clicks"]) or 0.0
    r = float(t["revenue"]) or 0.0
    return {
        "requests": q,
        "fill_rate": (f / q) if q else 0.0,
        "render_rate": (i / f) if f else 0.0,
        "ecpm": (r / i * 1000) if i else 0.0,
        "revenue": r,
        "fills": f,
        "impressions": i,
        "clicks": c,
    }


def decompose(db: DB, start: str, end: str, weeks: int = 4) -> Decomposition:
    res = db.query(
        _totals_sql(weeks),
        label="decompose:window_vs_baseline",
        params={"start": start, "end": end},
    )

    rows = {int(r["weeks_back"]): r for r in res.rows}
    actual_totals = rows[0]

    # Baseline totals are the mean of the comparable windows. Averaging the
    # additive totals (not the ratios) is what keeps the identity intact on the
    # baseline side too.
    prior = [rows[k] for k in range(1, weeks + 1) if k in rows]
    prior = [p for p in prior if float(p["requests"]) > 0]
    if not prior:
        raise ValueError("no comparable baseline windows available")

    # Median, not mean: the trailing weeks may themselves contain an anomaly.
    baseline_totals = {
        col: median([float(p[col]) for p in prior])
        for col in ("requests", "fills", "impressions", "clicks", "revenue")
    }

    a = _metrics_from(actual_totals)
    b = _metrics_from(baseline_totals)

    total_log = math.log(a["revenue"] / b["revenue"]) if a["revenue"] > 0 and b["revenue"] > 0 else 0.0
    revenue_pct = (a["revenue"] - b["revenue"]) / b["revenue"] if b["revenue"] else 0.0

    factors: list[FactorMove] = []
    sum_log = 0.0
    for name in FACTORS:
        av, bv = a[name], b[name]
        log_change = math.log(av / bv) if av > 0 and bv > 0 else 0.0
        sum_log += log_change
        factors.append(FactorMove(
            factor=name,
            actual=av,
            baseline=bv,
            pct_change=(av - bv) / bv if bv else 0.0,
            log_change=log_change,
            contribution_share=(log_change / total_log) if total_log else 0.0,
            contribution_pct_points=revenue_pct * (log_change / total_log) if total_log else 0.0,
        ))

    # If the four factors do not reconstruct the revenue movement, the
    # decomposition is incomplete and every downstream number is suspect.
    residual = total_log - sum_log

    factors.sort(key=lambda f: abs(f.log_change), reverse=True)

    return Decomposition(
        window_start=start,
        window_end=end,
        baseline_weeks_used=len(prior),
        actual={k: round(v, 6) for k, v in a.items()},
        baseline={k: round(v, 6) for k, v in b.items()},
        revenue_pct_change=revenue_pct,
        factors=factors,
        primary_factor=factors[0].factor,
        identity_residual=residual,
    )
