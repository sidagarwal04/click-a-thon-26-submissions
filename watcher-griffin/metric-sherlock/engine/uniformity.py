"""Spread analysis: is a deviation CONCENTRATED in one slice, or UNIFORM across
many? That single distinction is what separates the mechanisms in the signature
matrix, and it is measured here.

THE KEY REALISATION: NO EXTRA QUERIES ARE NEEDED
------------------------------------------------
The obvious way to answer "is this fill drop uniform across apps?" is to issue a
new query grouping by app. But the sweep has ALREADY evaluated every app against
its own band, in the same pass, along with every region, device, format and
advertiser. The spread of a deviation is therefore readable directly off the
sweep's own results:

    for scope_type 'app':  247 of 1,904 evaluated apps breached  -> 13% - concentrated
    for scope_type 'app': 1,733 of 1,904 evaluated apps breached -> 91% - uniform

This matters for three reasons, in order of importance:

1. TRACEABILITY. The numbers behind a mechanism claim are the same numbers already
   logged in the sweep's own queries, so "uniform across apps" cites evidence a
   judge can already see, rather than a separate query whose consistency with the
   detection has to be taken on trust.
2. CORRECTNESS. A fresh query would compare apps against a differently-derived
   baseline than the one that flagged the incident, so the two could disagree.
   Reading the sweep guarantees one definition of "abnormal" throughout.
3. COST. Free, versus one query per partner dimension per incident.

The fallback path -- `spread_from_queries` -- exists for the case the sweep cannot
cover: a specific 2-D slice inside an investigation, where the relevant scope was
not part of the sweep matrix. It is used deliberately and its SQL is logged.

WHAT "UNIFORM" MEANS NUMERICALLY
--------------------------------
Two numbers, because either alone is misleading:

  breadth  = breached entities / evaluated entities
             How widely did it happen? High breadth means the cause is upstream of
             this dimension.
  concentration = |impact of the top entity| / |impact of all breaching entities|
             How much of the money sits in one place? High concentration means the
             cause IS this dimension.

A cause is attributed to the dimension where concentration is high and breadth is
low, at the coarsest level where that still holds -- which is exactly the rule
that turns one demand outage into one incident instead of 300 app alerts.
"""

from dataclasses import dataclass, field
from typing import Optional

from engine.scopes import SCOPE_REGISTRY, partner_dimensions, scope

# Thresholds for turning the two numbers into words. Deliberately explicit
# constants rather than magic inline numbers, because these are the dials that
# decide how a mechanism is named, and the backtest tunes them.
# STRICTLY above 0.50, not at-or-above. At exactly 0.50 the system used to assert two
# contradictory things about the same number: `_uniform()` read >= 0.50 as "spread, so the
# cause lies upstream", while `seasonality_disproof` read <= 0.50 as "isolated, so
# seasonality cannot explain it". Both fired at 0.50.
#
# That was not an edge case. `os_family` has exactly two values, so 1-of-2 breached = 0.50
# is the single most common sibling shape in the system -- the most frequent case landed
# precisely on the contradiction, and still scored a full 15/15 for seasonality.
#
# Half is not "spread". One of two moving while the other held is the textbook isolated
# case, so 0.50 now reads as isolated-and-not-uniform, which is both self-consistent and
# the correct reading.
UNIFORM_BREADTH = 0.50        # STRICTLY above this share of entities breaching -> "uniform"
CONCENTRATED_BREADTH = 0.25   # at/below this -> "concentrated"
DOMINANT_CONCENTRATION = 0.60  # one entity holding this much of the impact -> "dominated by"


@dataclass
class SpreadStat:
    """How one dimension's entities behaved for one metric and direction."""

    scope_type: str
    evaluated: int = 0
    # DISTINCT entity values that breached -- not the number of breach rows.
    #
    # This distinction is load-bearing and was originally got wrong: one entity
    # breaching on six metrics produced breached=6 against evaluated=2 for a
    # two-valued dimension like os_family, which made breadth 300% and drove the
    # isolation term in cluster.py negative. The visible symptom was that every
    # incident was attributed to `global` -- the correct root, os_family=Android,
    # scored zero. Counting entities is what "how widely did this happen?" means.
    breaching_values: set = field(default_factory=set)
    breach_rows: int = 0        # how many (entity, metric) verdicts, for reporting
    top_value: str = ""
    top_impact_usd: float = 0.0
    total_impact_usd: float = 0.0
    source_steps: list = field(default_factory=list)

    @property
    def breached(self) -> int:
        return len(self.breaching_values)

    @property
    def breadth(self) -> float:
        # Clamped: `evaluated` is summed across metrics in the coverage rows while
        # `breached` counts distinct entities, so on a partially-evaluated
        # dimension the ratio could otherwise drift above 1.
        return min(1.0, self.breached / self.evaluated) if self.evaluated else 0.0

    @property
    def concentration(self) -> float:
        return (abs(self.top_impact_usd) / abs(self.total_impact_usd)) if self.total_impact_usd else 0.0

    @property
    def verdict(self) -> str:
        if self.evaluated == 0:
            return "not_evaluated"
        if self.breached == 0:
            return "flat"
        if self.breadth > UNIFORM_BREADTH:
            return "uniform"
        if self.breadth <= CONCENTRATED_BREADTH:
            return "concentrated"
        return "mixed"

    def as_reason(self) -> str:
        """Plain English with the numbers inline, suitable for a ruled-out list."""
        if self.evaluated == 0:
            return f"{self.scope_type}: not evaluated at this grain, so not used as evidence"
        if self.breached == 0:
            return (
                f"{self.scope_type}: all {self.evaluated} evaluated entities stayed within band -- "
                f"this dimension is flat and is ruled out as the cause"
            )
        pct = self.breadth * 100
        base = (
            f"{self.scope_type}: {self.breached} of {self.evaluated} entities breached ({pct:.0f}%)"
        )
        if self.verdict == "uniform":
            return (
                base + f" -- the deviation is spread across this dimension, so the cause lies "
                f"upstream of it, not in any one {self.scope_type}"
            )
        if self.verdict == "concentrated":
            extra = ""
            if self.concentration >= DOMINANT_CONCENTRATION:
                extra = (f", and '{self.top_value}' alone accounts for "
                         f"{self.concentration:.0%} of the dollar impact")
            return base + f" -- concentrated in this dimension{extra}"
        return base + " -- neither clearly concentrated nor clearly spread"


def spread_profile(verdicts: list, coverage: list, metric: Optional[str] = None,
                   direction: Optional[str] = None, grain: Optional[str] = None) -> dict:
    """{scope_type: SpreadStat} computed from a sweep's own results.

    Filters are optional but usually all three are given: mixing metrics or
    directions would average away the very contrast being measured (an
    above-band CTR and a below-band fill rate are not the same event).
    """
    # MAX across metrics, not SUM: coverage rows are per (scope, metric, grain),
    # so summing them counts the same entity once per metric and inflates the
    # denominator. The question is "how many entities of this dimension were
    # looked at", and that is the per-metric count, not its total.
    evaluated_by_scope = {}
    # SOURCE STEPS COME FROM THE COVERAGE ROWS, NOT ONLY FROM BREACHES.
    #
    # They used to be recorded only in the verdict loop below, which meant a dimension
    # with NO breaches carried none -- and those are precisely the ruled-out dimensions,
    # so the strongest claim the system makes ("all 71 entities of this dimension stayed
    # within band, so it is not the cause") was the one with no query behind it. The
    # field was populated, typed and rendered end to end and still showed nothing:
    # SpreadBars guards on a non-empty list, so the citation silently never appeared.
    #
    # A ruled-out dimension is evidenced by its EVALUATION, which is exactly what a
    # coverage row records -- so that is where the step belongs.
    steps_by_scope: dict = {}
    for c in coverage:
        if c.metric == "*":
            continue
        if metric and c.metric != metric:
            continue
        if grain and c.grain != grain:
            continue
        prev = evaluated_by_scope.get(c.scope_type, 0)
        evaluated_by_scope[c.scope_type] = max(prev, c.entities_evaluated)
        steps_by_scope.setdefault(c.scope_type, []).append(
            f"sweep:{c.scope_type}:{c.grain}:windows"
        )

    stats = {}
    for st, n_eval in evaluated_by_scope.items():
        stats[st] = SpreadStat(scope_type=st, evaluated=n_eval)
        # dict.fromkeys rather than a set: order is stable, which matters because the UI
        # cites source_steps[0] and a citation that reshuffles between reloads reads as
        # unreliable even when every entry is correct.
        stats[st].source_steps.extend(dict.fromkeys(steps_by_scope.get(st, [])))

    for v in verdicts:
        if metric and v.metric != metric:
            continue
        if direction and v.direction != direction:
            continue
        if grain and v.grain != grain:
            continue
        st = stats.setdefault(v.scope_type, SpreadStat(scope_type=v.scope_type))
        st.breach_rows += 1
        st.breaching_values.add(v.scope_value)
        impact = abs(getattr(v, "impact_usd", 0.0))
        st.total_impact_usd += impact
        if impact >= abs(st.top_impact_usd):
            st.top_impact_usd = impact
            st.top_value = v.scope_value
        step = f"sweep:{v.scope_type}:{v.grain}:windows"
        if step not in st.source_steps:
            st.source_steps.append(step)
    return stats


def partner_profile(root_scope_type: str, stats: dict) -> dict:
    """Only the dimensions INDEPENDENT of the root -- the ones whose spread is
    actually evidence about the root's cause.

    Independence is by entity root (engine/scopes.partner_dimensions), not by
    column name: an app's category is a function of its apps, so 'uniform across
    categories' when one app broke is an artefact of the broken app, not
    corroboration. Including it would let the signature matrix confirm itself.
    """
    if root_scope_type not in SCOPE_REGISTRY:
        return {}
    partners = {s.name for s in partner_dimensions(scope(root_scope_type))}
    return {k: v for k, v in stats.items() if k in partners}


def sibling_spread(root_scope_type: str, root_value: str, verdicts: list, coverage: list,
                   metric: str, direction: str, grain: Optional[str] = None) -> SpreadStat:
    """How the OTHER values of the root's own dimension behaved.

    This is the seasonality disproof, and it is a different question from partner
    spread. Seasonality moves people, and people carry every device and use every
    OS -- so a genuinely seasonal dip moves iOS and Android together. Android
    collapsing while iOS stays flat cannot be seasonal, whatever the calendar says.

    Returns the stat for the root's own scope_type, from which the caller can see
    both how many siblings moved and whether the root dominates the impact.
    """
    stats = spread_profile(verdicts, coverage, metric=metric, direction=direction, grain=grain)
    return stats.get(root_scope_type, SpreadStat(scope_type=root_scope_type))


def spread_from_queries(client, trace, scope_types: list, metric: str, grain_name: str,
                        filters: list, window: tuple, baseline_window: tuple) -> dict:
    """Fallback spread measurement for a slice the sweep did not cover.

    Used only inside an investigation, when a specific pinned slice (e.g. one app
    x one region) needs its spread measured across a dimension the sweep matrix
    does not contain. Each query is logged verbatim in the trace exactly as it
    runs, per the guardrail on raw fallbacks -- the point of naming this path
    separately is that a reader can tell which numbers came from the always-on
    sweep and which were computed on demand.
    """
    from engine.config import METRIC_DEFS
    from engine.drilldown import _combined_filter_expr

    spec = METRIC_DEFS[metric]
    out = {}
    where_extra = f" AND {_combined_filter_expr(filters)}" if filters else ""
    for st in scope_types:
        s = scope(st)
        if not s.raw_exprs:
            continue
        expr = s.raw_exprs[0]
        num_map = {"requests": "count()", "fills": "sum(is_filled)",
                   "impressions": "sum(is_impression)", "clicks": "sum(is_click)",
                   "revenue": "sum(revenue)"}
        num = num_map[spec.numerator]
        den = num_map.get(spec.denominator or "", "NULL")
        sql = (
            f"SELECT {expr} AS value, {num} AS numerator, {den} AS denominator "
            f"FROM ad_events WHERE event_time >= '{window[0]:%Y-%m-%d %H:%M:%S}' "
            f"AND event_time < '{window[1]:%Y-%m-%d %H:%M:%S}'{where_extra} "
            f"GROUP BY value ORDER BY numerator DESC LIMIT 200"
        )
        rows = client.query(sql, step=f"uniformity_raw:{st}:{metric}:current", trace=trace)
        out[st] = rows
    return out
