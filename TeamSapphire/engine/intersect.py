"""Stage 4c — intersection search. Compound segments, and when NOT to claim one.

MOTIVATION
----------
Review, 1 Aug: the localizer ranks each of the nine dimensions independently and
never tests combinations — while the problem statement's own worked example is a
compound segment: *"a drop in fill rate for Device X in Region North"*. Correct
catch, and our docs had been claiming a depth-3 recursion that did not exist.

THE TRAP THIS AVOIDS — which is the mirror of the single-dimension one
---------------------------------------------------------------------
Once you start testing pairs, the largest *absolute* contributor is always some
intersection, because slicing twice always produces a smaller, more extreme-
looking cell. Report the biggest pair and you will name a compound segment on
every incident, including the ones that are genuinely single-dimension.

Measured on the known Android 15 event: its fill rate fell to 0.4263–0.4421
across *all five* regions — uniform. EU nonetheless carries the largest absolute
share simply because EU has the most Android 15 traffic. A naive pair search
would confidently report "Android 15 in EU" and be wrong in a way that sounds
more precise than the truth.

So a compound is only reported when it explains materially MORE than its parts
already do. If the effect is uniform inside the parent segment, the parent alone
is the answer — the simpler claim that fits the evidence, not the narrower one
that merely sounds sharper.
"""
from dataclasses import dataclass, asdict
from typing import Any

from .db import DB
from .localize import FACTOR_NUMERATOR

# Dimension attributes were regenerated partway through the data: the same
# geo_device_id carries different values before and after DIM_EPOCH_CUT. The
# rollups handle this by building each period against its own tables, but the
# compound scan reads ad_events directly — an unpivoted rollup cannot represent
# combinations — so it must resolve per event.
#
# Measured before this existed: June's compound findings were computed with
# July's attribute assignment, and the 06-28 iOS 18.1 x APAC finding stopped
# reproducing because "iOS 18.1" no longer meant the same devices.
#
# Both epochs are their own immutable dictionary. Nothing reads the mutable
# inmobi.dict_* — on ClickHouse Cloud, SYSTEM RELOAD DICTIONARY reloads only the
# node it is issued against, so those returned the new mapping on one connection
# and the old one on another, making a pair scan's answer depend on which
# replica served it.
DIM_EPOCH_CUT = "2026-07-06 00:00:00"


def _epoch(old_expr: str, cur_expr: str) -> str:
    return f"if(event_time < '{DIM_EPOCH_CUT}', {old_expr}, {cur_expr})"


def _geo(attr: str) -> str:
    return _epoch(f"dictGetString('inmobi.dict_geo_device_old','{attr}', geo_device_id)",
                  f"dictGetString('inmobi.dict_geo_device_cur','{attr}', geo_device_id)")


def _app(attr: str) -> str:
    return _epoch(f"dictGetString('inmobi.dict_apps_old','{attr}', app_id)",
                  f"dictGetString('inmobi.dict_apps_cur','{attr}', app_id)")


def _adv(attr: str) -> str:
    inner = _epoch(f"dictGetString('inmobi.dict_advertisers_old','{attr}', advertiser_id)",
                   f"dictGetString('inmobi.dict_advertisers_cur','{attr}', advertiser_id)")
    return f"if(advertiser_id='', '(unfilled)', {inner})"


DIM_SQL = {
    "ad_format": "CAST(ad_format AS String)",
    "region": _geo("region"),
    "country": _geo("country"),
    "device_model": _geo("device_model"),
    "os_version": _geo("os_version"),
    "category": _app("category"),
    "publisher_tier": _app("publisher_tier"),
    "vertical": _adv("vertical"),
    "campaign_type": _adv("campaign_type"),
}

RAW_MEASURES = """
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
"""

# A compound must move at least this multiple of its parent before it is worth
# naming. Both the within-parent search and the standalone scan use this same
# definition — they previously encoded the same question two different ways
# (1.25x here, 2.0x there), which is how one of them stayed wrong for an hour.
PARENT_LIFT = 2.0
# Guards against a tiny cell looking extreme through sampling noise alone.
MIN_CELL_REQUESTS = 200


@dataclass
class Intersection:
    dim_a: str
    value_a: str
    dim_b: str
    value_b: str
    actual: float
    baseline: float
    pct_change: float
    parent_pct_change: float
    lift_over_parent: float     # how much more the cell moved than its parent
    share_of_parent_volume: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntersectionResult:
    parent_dim: str
    parent_value: str
    factor: str
    verdict: str                # "compound" | "uniform_within_parent" | "inconclusive"
    reason: str
    best: Intersection | None
    checked: list[Intersection]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_dim": self.parent_dim,
            "parent_value": self.parent_value,
            "factor": self.factor,
            "verdict": self.verdict,
            "reason": self.reason,
            "best": self.best.to_dict() if self.best else None,
            "checked": [c.to_dict() for c in self.checked],
        }


def _value_of(row: dict, factor: str) -> float:
    num_col, den_col = FACTOR_NUMERATOR[factor]
    num = float(row.get(num_col, 0) or 0)
    if den_col is None:
        return num
    den = float(row.get(den_col, 0) or 0)
    if den == 0:
        return 0.0
    v = num / den
    return v * 1000 if factor == "ecpm" else v


def find_intersections(
    db: DB, start: str, end: str, factor: str,
    parent_dim: str, parent_value: str, weeks: int = 1,
) -> IntersectionResult:
    """Within the responsible segment, test whether a second dimension concentrates it.

    Reads the raw table rather than the rollups: the unpivoted rollup carries one
    dimension per row by construction, so a pair has to be resolved from events.
    Bounded by the event window, so it is a filtered scan, not a full one.
    """
    parent_expr = DIM_SQL[parent_dim]
    others = [d for d in DIM_SQL if d != parent_dim]

    checked: list[Intersection] = []

    for dim_b in others:
        res = db.query(
            f"""
            SELECT
                window,
                {DIM_SQL[dim_b]} AS value_b,
                {RAW_MEASURES}
            FROM (
                SELECT *, 'actual' AS window FROM inmobi.ad_events
                WHERE event_time >= {{start:DateTime}} AND event_time <= {{end:DateTime}}
                  AND {parent_expr} = {{pv:String}}
                UNION ALL
                SELECT *, 'baseline' AS window FROM inmobi.ad_events
                WHERE event_time >= {{start:DateTime}} - toIntervalWeek({{weeks:UInt8}})
                  AND event_time <= {{end:DateTime}}   - toIntervalWeek({{weeks:UInt8}})
                  AND {parent_expr} = {{pv:String}}
            )
            GROUP BY window, value_b
            """,
            label=f"intersect:{parent_dim}={parent_value}x{dim_b}",
            params={"start": start, "end": end, "pv": parent_value, "weeks": weeks},
        )

        actual = {r["value_b"]: r for r in res.rows if r["window"] == "actual"}
        baseline = {r["value_b"]: r for r in res.rows if r["window"] == "baseline"}
        if not actual or not baseline:
            continue

        # The parent's own movement, recomputed from the same rows so the
        # comparison is exactly like-for-like.
        parent_actual = {c: sum(float(r[c]) for r in actual.values())
                         for c in ("requests", "fills", "impressions", "clicks", "revenue")}
        parent_baseline = {c: sum(float(r[c]) for r in baseline.values())
                           for c in ("requests", "fills", "impressions", "clicks", "revenue")}
        pa, pb = _value_of(parent_actual, factor), _value_of(parent_baseline, factor)
        if pb == 0:
            continue
        parent_pct = (pa - pb) / pb
        parent_volume = parent_actual["requests"] or 1.0

        for value_b, arow in actual.items():
            brow = baseline.get(value_b)
            if not brow or float(arow["requests"]) < MIN_CELL_REQUESTS:
                continue
            a, b = _value_of(arow, factor), _value_of(brow, factor)
            if b == 0:
                continue
            pct = (a - b) / b
            # Lift: how much further this cell moved than the parent as a whole.
            # Ratio, not excess-over-parent: same definition the standalone scan uses.
            lift = abs(pct) / max(abs(parent_pct), 1e-9)
            checked.append(Intersection(
                dim_a=parent_dim, value_a=parent_value, dim_b=dim_b, value_b=value_b,
                actual=a, baseline=b, pct_change=pct, parent_pct_change=parent_pct,
                lift_over_parent=lift,
                share_of_parent_volume=float(arow["requests"]) / parent_volume,
            ))

    if not checked:
        return IntersectionResult(
            parent_dim, parent_value, factor, "inconclusive",
            "no intersecting cell carried enough volume to test", None, [])

    checked.sort(key=lambda c: c.lift_over_parent, reverse=True)
    best = checked[0]
    spread = max(abs(c.pct_change) for c in checked) - min(abs(c.pct_change) for c in checked)

    if best.lift_over_parent >= PARENT_LIFT:
        verdict = "compound"
        reason = (
            f"{best.dim_b}={best.value_b} moved {best.pct_change:+.1%} inside "
            f"{parent_dim}={parent_value}, against {best.parent_pct_change:+.1%} for that "
            f"segment overall — {best.lift_over_parent:.0%} further than the parent, so the "
            f"effect is concentrated in the intersection rather than spread across it"
        )
    else:
        verdict = "uniform_within_parent"
        reason = (
            f"the movement is uniform inside {parent_dim}={parent_value}: across every "
            f"second dimension tested, the widest spread between cells is "
            f"{spread:.1%} and the most extreme cell moved only "
            f"{best.lift_over_parent:.1f}x the parent's {best.parent_pct_change:+.1%}. "
            f"No compound segment is responsible — {parent_dim}={parent_value} alone is the "
            f"correct scope"
        )

    return IntersectionResult(parent_dim, parent_value, factor, verdict, reason, best, checked[:12])


# ---------------------------------------------------------------------------
# Standalone 2-D scan — finds compound anomalies with no single-dimension parent
# ---------------------------------------------------------------------------
# find_intersections() above only searches *inside* a dimension the single-pass
# localizer already flagged. That is useless for the case that matters most:
#
#   2026-06-28, fill rate      global  -1.0%
#                              APAC    -4.5%   } both below the 8% materiality
#                              iPhone 14 -5.9% } gate, so neither is ever flagged
#                              APAC x iPhone 14  -23.2%   <- the actual anomaly
#
# Neither parent moves enough to be noticed, so no parent is ever handed to the
# intersection search and the anomaly is invisible by construction. This is the
# problem statement's own worked example ("a drop in fill rate for Device X in
# Region North"), and a single-dimension scan cannot see it in principle.
#
# So pairs are scanned directly, against the same like-for-like median baseline
# the rest of the system uses. The defining test of a *compound* anomaly is that
# the cell moved while BOTH its parents stayed put — if a parent moved too, the
# single-dimension scan already owns it and reporting the pair would just be a
# narrower restatement of the same finding.

SCAN_PAIRS = ("region", "device_model", "os_version", "category",
              "publisher_tier", "ad_format", "country")
MIN_CELL_PCT = 0.15        # the cell must move this much
MIN_PARENT_LIFT = PARENT_LIFT   # same definition as the within-parent search
MIN_SCAN_REQUESTS = 300    # per day, to keep counting noise out

# NOT "both parents must be flat". That rule looks right and is backwards: a
# compound cell large enough to matter DRAGS ITS OWN PARENT past any flatness
# threshold, so the bigger the finding, the more certainly it is rejected.
#
# Measured on 2026-06-28 fill rate:
#     iOS 18.1 x APAC     -50.6%   <- the real anomaly
#     iOS 18.1 alone      -12.3%   <- moved only because of the cell above
#     APAC alone           -2.3%
# A flatness rule with an 8% bar threw this away on the strength of the -12.3%,
# and the scan instead reported "APAC x iPhone 14" at -23.2% — a diluted proxy,
# since iPhone 14s largely run iOS 18.1. We named a weaker, partially-correct
# segment and missed the sharper true one.
#
# The right question is not whether the parents held still but whether the cell
# moved enough MORE than them to be a finding of its own.


@dataclass
class CompoundFinding:
    day: str
    dim_a: str
    value_a: str
    dim_b: str
    value_b: str
    metric: str
    actual: float
    baseline: float
    pct_change: float
    parent_a_pct: float
    parent_b_pct: float
    requests: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def scope(self) -> str:
        return f"{self.dim_a}={self.value_a} x {self.dim_b}={self.value_b}"


def scan_intersections(
    db: DB, start: str, end: str, metric: str = "fill_rate", weeks: int = 4,
    dims: tuple[str, ...] = SCAN_PAIRS,
    min_cell_pct: float = MIN_CELL_PCT,
    min_parent_lift: float = MIN_PARENT_LIFT,
    known_windows: list[tuple[str, str]] | None = None,
) -> tuple[list[CompoundFinding], list[dict]]:
    """Scan dimension pairs for anomalies invisible to any single dimension.

    Daily grain: a compound cell is small enough that hourly counting noise
    swamps the signal, and a genuine compound event lasts at least a day.

    KNOWN LIMIT — the grain is coarser than detection. Single-dimension
    detection runs hourly; this runs daily. A compound anomaly lasting only a
    few hours is therefore diluted across 24 and can fall under min_cell_pct.
    Accepted deliberately: at hourly grain a cell like iOS 18.1 x PH holds ~30
    requests, where binomial noise alone is ~±15% and the scan would produce
    mostly false positives. The trade is recall on short compound events for
    precision on the ones we can actually resolve. Raising MIN_SCAN_REQUESTS
    and dropping to hourly is the fix if a shorter compound event matters.

    `known_windows` are windows where a single-dimension anomaly has already
    been found. A strong single-dimension cause casts a shadow across every
    pair that correlates with it — the Android 15 fill collapse surfaced as
    "Pixel 7 x AE", "Galaxy A54 x ES" and dozens more, all of them the same
    event seen through a narrower slice, with parents moving only ~5% because
    Android 15 is a fraction of each. Findings inside a known window are
    reported separately rather than as new anomalies, so a real compound
    elsewhere is not buried under the shadow of one we already understand.
    """
    def in_known(day: str) -> bool:
        return any(w0[:10] <= day <= w1[:10] for w0, w1 in (known_windows or []))
    import itertools

    num_col, den_col = FACTOR_NUMERATOR[metric]
    agg = {"requests": "count()", "fills": "sum(is_filled)",
           "impressions": "sum(is_impression)", "clicks": "sum(is_click)",
           "revenue": "sum(revenue)"}
    num_sql, den_sql = agg[num_col], (agg[den_col] if den_col else None)
    value_sql = f"({num_sql}) / ({den_sql})" if den_sql else f"({num_sql})"

    findings: list[CompoundFinding] = []
    checked: list[dict] = []

    for a, b in itertools.combinations(dims, 2):
        sql = f"""
        WITH cells AS (
            SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow,
                   {DIM_SQL[a]} AS va, {DIM_SQL[b]} AS vb,
                   {value_sql} AS metric_value, count() AS requests
            FROM inmobi.ad_events
            WHERE event_time >= {{start:DateTime}} - toIntervalWeek({{weeks:UInt8}})
              AND event_time <= {{end:DateTime}}
            GROUP BY day, dow, va, vb
            HAVING requests >= {{minreq:UInt32}}
        ),
        pa AS (
            SELECT toDate(event_time) AS day, {DIM_SQL[a]} AS va, {value_sql} AS v
            FROM inmobi.ad_events
            WHERE event_time >= {{start:DateTime}} - toIntervalWeek({{weeks:UInt8}})
              AND event_time <= {{end:DateTime}}
            GROUP BY day, va
        ),
        pb AS (
            SELECT toDate(event_time) AS day, {DIM_SQL[b]} AS vb, {value_sql} AS v
            FROM inmobi.ad_events
            WHERE event_time >= {{start:DateTime}} - toIntervalWeek({{weeks:UInt8}})
              AND event_time <= {{end:DateTime}}
              GROUP BY day, vb
        )
        SELECT t.day AS day, t.va AS va, t.vb AS vb,
               t.metric_value AS actual, t.requests AS requests,
               quantileExact(0.5)(h.metric_value) AS baseline,
               any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base,
               any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base
        FROM cells AS t
        INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day
        INNER JOIN pa AS pa_now  ON pa_now.day = t.day AND pa_now.va = t.va
        INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day
        INNER JOIN pb AS pb_now  ON pb_now.day = t.day AND pb_now.vb = t.vb
        INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day
        WHERE t.day >= toDate({{start:DateTime}})
        GROUP BY day, va, vb, actual, requests
        """
        res = db.query(sql, label=f"scan_intersect:{a}x{b}",
                       params={"start": start, "end": end, "weeks": weeks,
                               "minreq": MIN_SCAN_REQUESTS})
        flagged = 0
        for r in res.rows:
            base = float(r["baseline"])
            if base == 0:
                continue
            pct = (float(r["actual"]) - base) / base
            pa_b, pb_b = float(r["pa_base"]), float(r["pb_base"])
            pa_pct = (float(r["pa_now"]) - pa_b) / pa_b if pa_b else 0.0
            pb_pct = (float(r["pb_now"]) - pb_b) / pb_b if pb_b else 0.0

            # The defining condition: the cell moved, and it moved
            # substantially more than either parent — so the parent's own
            # movement is a consequence of this cell rather than an
            # explanation for it.
            strongest_parent = max(abs(pa_pct), abs(pb_pct), 1e-9)
            lift = abs(pct) / strongest_parent
            if abs(pct) >= min_cell_pct and lift >= min_parent_lift:
                flagged += 1
                findings.append(CompoundFinding(
                    day=str(r["day"]), dim_a=a, value_a=r["va"], dim_b=b, value_b=r["vb"],
                    metric=metric, actual=float(r["actual"]), baseline=base,
                    pct_change=pct, parent_a_pct=pa_pct, parent_b_pct=pb_pct,
                    requests=int(r["requests"])))
        checked.append({"pair": f"{a} x {b}", "cells_examined": len(res.rows),
                        "flagged": flagged, "query_ms": round(res.query_ms, 1),
                        "rows_read": res.rows_read})

    novel = [f for f in findings if not in_known(f.day)]
    shadowed = [f for f in findings if in_known(f.day)]
    novel.sort(key=lambda f: abs(f.pct_change), reverse=True)
    shadowed.sort(key=lambda f: abs(f.pct_change), reverse=True)
    checked.append({"pair": "(summary)", "novel": len(novel),
                    "inside_known_windows": len(shadowed)})
    return novel, checked
