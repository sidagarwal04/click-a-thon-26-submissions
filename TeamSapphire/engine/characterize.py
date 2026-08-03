"""Stage 4b — characterization. The step between "which segment" and "why".

MOTIVATION
----------
The question this stage exists to answer: *"the real question isn't 'did it move?' — an alert
already answers that. The question is 'why?'"*

Fair. Naming the factor and the segment is a sharper "what", not a "why".
"Android 15 fill rate fell 44.9%" still leaves an on-call engineer with the
whole diagnosis ahead of them.

But a lot of the "why" is already sitting in the data we query, unread — in the
*shape* of the transition rather than its size:

  * A change that lands inside a single hour was switched, not degraded.
    Organic decay, capacity exhaustion and traffic-mix drift all ramp.
  * A change that lands exactly on a day boundary was scheduled by something
    that thinks in days: a campaign flight, a config push, a nightly job.
  * A change that reverses cleanly after a whole number of days had an end
    date. Outages do not end tidily at midnight.
  * A factor that did NOT move rules out whole classes of cause. Requests flat
    while fill collapses means demand-side, not traffic, not tracking.

None of this identifies the mechanism — that lives in systems we cannot see.
What it does is cut the search space from "everything" to "scheduled demand-side
configuration affecting one OS version", which is the difference between a
diagnosis an engineer can act on and a number they have to go investigate.

Every conclusion here stays evidence-backed: shape and alignment are measured,
and the reading is stated as what the pattern is consistent with, never as an
established mechanism.
"""
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any

from .db import DB
from .localize import FACTOR_NUMERATOR

# A transition is "sharp" when this much of the total change happens in one hour.
SHARP_STEP_FRACTION = 0.7
# "Held steady" is relative, not absolute. The dataset has a slow growth trend,
# so a week-over-week comparison shows a few percent on a metric that did not
# really move — a fixed 2% threshold rejected requests at +2.5% while fill rate
# had collapsed 44%. A factor is steady when it moved little in absolute terms
# AND was dwarfed by the factor under investigation.
UNCHANGED_PCT = 0.05
STEADY_RATIO = 0.2   # at most a fifth of the primary factor's movement


@dataclass
class Transition:
    at_hour: str
    before: float
    after: float
    change: float
    step_fraction: float      # share of the total move landing in this single hour
    shape: str                # "step" | "gradual"
    aligns_to_day_boundary: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Signature:
    factor: str
    scope: str
    onset: Transition | None
    recovery: Transition | None
    duration_hours: int | None
    held_steady: list[str] = field(default_factory=list)
    reading: str = ""
    rules_out: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor": self.factor,
            "scope": self.scope,
            "onset": self.onset.to_dict() if self.onset else None,
            "recovery": self.recovery.to_dict() if self.recovery else None,
            "duration_hours": self.duration_hours,
            "held_steady": self.held_steady,
            "reading": self.reading,
            "rules_out": self.rules_out,
        }


def _metric_expr(factor: str) -> str:
    num, den = FACTOR_NUMERATOR[factor]
    if den is None:
        return num
    expr = f"if({den} > 0, {num} / {den}, 0)"
    return f"({expr}) * 1000" if factor == "ecpm" else expr


def _find_transition(series: list[tuple[str, float]], level_before: float,
                     level_after: float) -> Transition | None:
    """Locate the hour carrying the largest single-hour move, and measure it.

    step_fraction is what separates a switch from a slide: if one hour carries
    most of the total change, something was toggled at that instant. If the
    change is spread across many hours, it degraded.
    """
    if len(series) < 2:
        return None
    total = level_after - level_before
    if abs(total) < 1e-12:
        return None

    best_i, best_delta = None, 0.0
    for i in range(1, len(series)):
        delta = series[i][1] - series[i - 1][1]
        if abs(delta) > abs(best_delta):
            best_i, best_delta = i, delta

    if best_i is None:
        return None

    at = series[best_i][0]
    fraction = abs(best_delta / total)
    return Transition(
        at_hour=at,
        before=round(series[best_i - 1][1], 6),
        after=round(series[best_i][1], 6),
        change=round(best_delta, 6),
        step_fraction=round(min(fraction, 1.0), 4),
        shape="step" if fraction >= SHARP_STEP_FRACTION else "gradual",
        aligns_to_day_boundary=datetime.fromisoformat(at).hour == 0,
    )


def characterize(db: DB, start: str, end: str, factor: str,
                 dim_name: str | None = None, dim_value: str | None = None,
                 context_hours: int = 6) -> Signature:
    """Measure the shape of the transition into and out of an event."""
    scope = f"{dim_name}={dim_value}" if dim_name else "global"
    expr = _metric_expr(factor)

    if dim_name and dim_value:
        source, filt = "inmobi.events_hourly_by_dim", \
            "AND dim_name = {dim_name:String} AND dim_value = {dim_value:String}"
    else:
        source, filt = "inmobi.events_hourly", ""

    res = db.query(
        f"""
        SELECT hour,
               {expr}                                   AS metric_value,
               {_metric_expr('requests')}                AS requests,
               {_metric_expr('fill_rate')}               AS fill_rate,
               {_metric_expr('render_rate')}             AS render_rate,
               {_metric_expr('ecpm')}                    AS ecpm
        FROM {source}
        WHERE hour >= {{start:DateTime}} - toIntervalHour({{ctx:UInt16}})
          AND hour <= {{end:DateTime}}   + toIntervalHour({{ctx:UInt16}})
          {filt}
        ORDER BY hour
        """,
        label=f"characterize:{factor}:{scope}",
        params={"start": start, "end": end, "ctx": context_hours,
                **({"dim_name": dim_name, "dim_value": dim_value} if dim_name else {})},
    )
    rows = res.rows
    if len(rows) < 4:
        return Signature(factor=factor, scope=scope, onset=None, recovery=None,
                         duration_hours=None,
                         reading="too few hours to characterise the transition")

    inside = [r for r in rows if start <= str(r["hour"]) <= end]
    before = [r for r in rows if str(r["hour"]) < start]
    after = [r for r in rows if str(r["hour"]) > end]
    if not inside:
        return Signature(factor=factor, scope=scope, onset=None, recovery=None,
                         duration_hours=None, reading="event window not present in data")

    def level(rs):
        vals = [float(r["metric_value"]) for r in rs]
        return sum(vals) / len(vals) if vals else 0.0

    lvl_before, lvl_inside, lvl_after = level(before), level(inside), level(after)

    onset = _find_transition(
        [(str(r["hour"]), float(r["metric_value"])) for r in before + inside[:2]],
        lvl_before, lvl_inside) if before else None
    recovery = _find_transition(
        [(str(r["hour"]), float(r["metric_value"])) for r in inside[-2:] + after],
        lvl_inside, lvl_after) if after else None

    # A factor that stayed flat through the event is evidence, not absence of it.
    #
    # Compared against the SAME hours one week earlier, not against the hours
    # immediately before. The first version of this compared a 6-hour evening
    # trough to a 72-hour window spanning whole days, so a perfectly flat metric
    # read as moved purely from the time-of-day mix — the same like-for-like
    # mistake the detector exists to prevent, reintroduced in new code.
    held_steady, rules_out = [], []
    prior = db.query(
        f"""
        SELECT {_metric_expr('requests')}    AS requests,
               {_metric_expr('fill_rate')}   AS fill_rate,
               {_metric_expr('render_rate')} AS render_rate,
               {_metric_expr('ecpm')}        AS ecpm
        FROM {source}
        WHERE hour >= {{start:DateTime}} - toIntervalWeek(1)
          AND hour <= {{end:DateTime}}   - toIntervalWeek(1)
          {filt}
        """,
        label=f"characterize:baseline:{scope}",
        params={"start": start, "end": end,
                **({"dim_name": dim_name, "dim_value": dim_value} if dim_name else {})},
    ).rows

    def pct_move(col: str) -> float | None:
        b = sum(float(r[col]) for r in prior) / len(prior)
        i = sum(float(r[col]) for r in inside) / len(inside)
        return abs((i - b) / b) if b else None

    primary_move = pct_move(factor) if prior else None
    for other in ("requests", "fill_rate", "render_rate", "ecpm"):
        if other == factor or not prior:
            continue
        moved = pct_move(other)
        if moved is None:
            continue
        dwarfed = primary_move is None or moved <= primary_move * STEADY_RATIO
        if moved < UNCHANGED_PCT and dwarfed:
            held_steady.append(other)

    if "requests" in held_steady:
        rules_out.append(
            "a traffic or tracking problem — request volume was unchanged, so "
            "the same demand arrived and was handled differently"
        )
    if factor == "requests" and "fill_rate" in held_steady:
        rules_out.append(
            "a supply or demand-quality problem — everything that did arrive "
            "filled and rendered normally, so fewer requests arrived at all"
        )

    duration = len(inside)
    reading = _read(onset, recovery, duration, factor, held_steady)

    return Signature(factor=factor, scope=scope, onset=onset, recovery=recovery,
                     duration_hours=duration, held_steady=held_steady,
                     reading=reading, rules_out=rules_out)


def _read(onset: Transition | None, recovery: Transition | None,
          duration: int, factor: str, held_steady: list[str]) -> str:
    """Say what the shape is consistent with — never what caused it."""
    if onset is None:
        return "no clean transition into the window; the change may predate the data"

    bits: list[str] = []

    if onset.shape == "step":
        bits.append(
            f"{factor} changed within a single hour at {onset.at_hour} "
            f"({onset.before:.4g} to {onset.after:.4g}), with "
            f"{onset.step_fraction:.0%} of the total movement landing in that one "
            f"hour — a switch, not a slide"
        )
    else:
        bits.append(
            f"{factor} moved gradually into the window, the largest single hour "
            f"carrying {onset.step_fraction:.0%} of the change — consistent with a "
            f"rollout or progressive degradation rather than a single change"
        )

    if onset.aligns_to_day_boundary:
        bits.append(
            "the change lands exactly on a day boundary, which points at something "
            "that schedules in days — a campaign flight, a config push, a nightly job — "
            "rather than an organic failure"
        )

    if recovery and recovery.shape == "step":
        clean_days = duration % 24 == 0
        bits.append(
            f"it reverses just as sharply at {recovery.at_hour}"
            + (f" after exactly {duration // 24} day(s)" if clean_days else
               f" after {duration} hours")
            + ", which is the signature of a defined end date rather than a fix"
        )
    elif recovery:
        bits.append(f"it recovers gradually from {recovery.at_hour}")
    else:
        bits.append("it had not recovered by the end of the data")

    if held_steady:
        bits.append(
            "meanwhile " + ", ".join(held_steady) + " held steady through the window"
        )

    return "; ".join(bits) + "."
