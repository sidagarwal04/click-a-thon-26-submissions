"""Dollar impact: how much money a breach represents.

WHY THIS EXISTS AT ALL
----------------------
A deviation score answers "how unusual is this?". Nobody prioritises work on that
question. `impact_usd` answers "how much is this costing?", which is the question
that decides whether something is an incident or a curiosity, and it is why
severity in this system is ranked on dollars rather than sigmas: a 6-sigma move
in a slice earning $0.20/day is arithmetically striking and commercially
irrelevant, while a 3-sigma move on 15% of revenue is neither.

THE ESTIMATOR, AND WHY IT IS FILL-BASED
---------------------------------------
    impact = (seasonally expected units - actual units) x revenue per unit

Two deliberate choices:

1. EXPECTED comes from the seasonal band centre, never from a period average.
   This is not a refinement, it is the difference between a right and a wrong
   answer. A naive "compare to the last N days' average" lands on whichever
   weekdays the window happens to contain: on this dataset Tuesday earns ~$521
   and Sunday ~$397, a 24% spread, so an incident spanning Tue-Thu compared
   against a flat average can come out looking POSITIVE. The band centre is
   already weekday- and hour-matched, so it does not have that failure mode.

2. Prefer the FILL count as the unit, not raw revenue delta. Revenue is the
   noisiest series in the funnel -- it moves with volume, fill, render and price
   at once -- so differencing it attributes everything to whatever broke last.
   Missing fills times revenue-per-fill isolates the demand shortfall itself.
   Where fills are not the thing that moved (a render bug, a pricing shift) the
   estimator falls back to the metric's own numerator, and says which basis it
   used.

EVERY NUMBER IS RECOMPUTABLE
----------------------------
`detail` carries the actual inputs -- expected units, actual units, the
revenue-per-unit rate and where it came from -- so a reader can multiply them out
by hand and get the same figure. An impact number that cannot be checked is
exactly the kind of authoritative-looking figure the guardrails exist to prevent.

WHAT THIS DOES NOT CLAIM
------------------------
This is an exposure estimate, not an accounting reconciliation. It assumes the
missing units would have monetised at the rate the surviving units did, which is
the standard assumption and is stated rather than buried. Where the inputs do not
support any estimate, impact is 0.0 with basis 'unavailable' -- never a guess.
"""

from dataclasses import dataclass, field
from typing import Optional

from engine.bands import Band, BandVerdict, resolve_band
from engine.config import METRIC_DEFS, settings
from engine.grains import GrainSpec

# Metrics whose movement implies a shortfall in FILLS, so the fill-based
# estimator is the right one. Everything else is priced off its own numerator.
_FILL_DRIVEN = {"fill_rate", "fills"}

# Why a click shortfall books $0 of revenue exposure on this dataset. Module-level
# because two places have to say it in exactly the same words: the impact estimate
# itself, and the causal chain that explains the estimate to a reader
# (engine/causal_chain.py). Two hand-written copies of the same justification drift,
# and the moment they disagree the explanation stops being evidence.
ENGAGEMENT_ZERO_EXPOSURE_BASIS = "no revenue exposure (clicks do not carry revenue here)"
ENGAGEMENT_ZERO_EXPOSURE_REASON = (
    "revenue accrues on impressions in this dataset, not on clicks: "
    "revenue/impression is 0.00247 for CPC, CPI and CPM alike. A click-rate move "
    "with unchanged impressions therefore has no revenue effect. Recorded as a "
    "diagnostic signal; genuine revenue loss is detected by the revenue and ecpm "
    "metrics, which carry their own bands."
)


@dataclass
class ImpactEstimate:
    impact_usd: float = 0.0
    basis: str = "unavailable"
    detail: dict = field(default_factory=dict)

    def as_reason(self) -> str:
        if self.basis == "unavailable":
            return "no dollar impact could be estimated from the available evidence"
        d = self.detail
        return (
            f"{self.basis}: expected {d.get('expected_units', 0):,.1f} {d.get('unit', 'units')} vs "
            f"actual {d.get('actual_units', 0):,.1f} "
            f"({d.get('missing_units', 0):+,.1f}) at {d.get('revenue_per_unit', 0):.6g} "
            f"$/{d.get('unit', 'unit')} ({d.get('rate_source', 'n/a')}) = ${self.impact_usd:,.2f}"
        )


def _band_center(per_metric_bands: dict, scope_value: str, g: GrainSpec, window_start, metric: str) -> Optional[float]:
    """The seasonal expectation for another metric on the same slice, if a band
    for it exists. Returns None rather than falling back to an average -- an
    unavailable expectation must not be silently replaced by a biased one."""
    by_cell = per_metric_bands.get(scope_value, {}) if per_metric_bands else {}
    band = resolve_band(by_cell, g, window_start)
    if band is None or not band.usable:
        return None
    return band.center


def estimate_impact(
    verdict: BandVerdict,
    measures: dict,
    band: Band,
    bands_for_metric: dict,
    g: GrainSpec,
    prefix: str = "cur",
    all_bands: Optional[dict] = None,
) -> ImpactEstimate:
    """Dollar exposure for one confirmed breach.

    `measures` is the summed-measures row for this entity and window;
    `bands_for_metric` is {scope_value: {cell: Band}} for the breached metric;
    `all_bands` optionally maps metric -> that same structure, which lets the
    fill-based estimator find the `fills` band on the same slice.
    """
    spec = METRIC_DEFS[verdict.metric]
    sv = verdict.scope_value
    actual_revenue = float(measures.get(f"{prefix}_revenue") or 0)
    actual_fills = float(measures.get(f"{prefix}_fills") or 0)
    actual_impressions = float(measures.get(f"{prefix}_impressions") or 0)
    actual_requests = float(measures.get(f"{prefix}_requests") or 0)

    # --- fill-driven metrics: missing fills x revenue per fill ---
    if verdict.metric in _FILL_DRIVEN:
        if verdict.metric == "fill_rate":
            # Expected fills = expected fill RATE x the requests that actually
            # arrived. Using expected requests as well would conflate a traffic
            # change with a demand change and double-count one incident as two.
            expected_fills = band.center * actual_requests
        else:
            expected_fills = band.center
        missing = expected_fills - actual_fills
        if actual_fills > 0:
            rev_per_fill, rate_src = actual_revenue / actual_fills, "observed revenue/fill in this window"
        else:
            rev_per_fill, rate_src = 0.0, "no fills in window -- no observed rate"
        if rev_per_fill <= 0:
            return ImpactEstimate(0.0, "unavailable", {
                "reason": "no revenue-per-fill could be observed for this slice/window",
                "actual_fills": actual_fills, "expected_fills": expected_fills,
            })
        return ImpactEstimate(
            impact_usd=missing * rev_per_fill,
            basis="fill-based (missing fills x observed revenue/fill)",
            detail={
                "unit": "fills", "expected_units": expected_fills, "actual_units": actual_fills,
                "missing_units": missing, "revenue_per_unit": rev_per_fill, "rate_source": rate_src,
                "actual_requests": actual_requests, "band_center": band.center,
                "seasonal_cell": band.seasonal_cell,
            },
        )

    # --- revenue itself: the band centre IS the expectation ---
    if verdict.metric == "revenue":
        missing = band.center - actual_revenue
        return ImpactEstimate(
            impact_usd=missing,
            basis="direct (seasonally expected revenue minus actual)",
            detail={
                "unit": "dollars", "expected_units": band.center, "actual_units": actual_revenue,
                "missing_units": missing, "revenue_per_unit": 1.0,
                "rate_source": "revenue is already money", "seasonal_cell": band.seasonal_cell,
            },
        )

    # --- eCPM / rpr: a price move applied to the volume that actually occurred ---
    if verdict.metric in ("ecpm", "rpr"):
        unit_count = actual_impressions if verdict.metric == "ecpm" else actual_requests
        unit_name = "impressions" if verdict.metric == "ecpm" else "requests"
        divisor = 1000.0 if verdict.metric == "ecpm" else 1.0
        missing_rate = band.center - verdict.value
        return ImpactEstimate(
            impact_usd=missing_rate * unit_count / divisor,
            basis=f"price-based (expected minus actual {verdict.metric} x actual {unit_name})",
            detail={
                "unit": unit_name, "expected_units": band.center, "actual_units": verdict.value,
                "missing_units": missing_rate, "revenue_per_unit": unit_count / divisor,
                "rate_source": f"actual {unit_name} in window", "seasonal_cell": band.seasonal_cell,
            },
        )

    # --- render_rate: fills were bought but not shown, so the loss is the
    #     revenue those unshown impressions would have earned ---
    if verdict.metric == "render_rate":
        expected_impressions = band.center * actual_fills
        missing = expected_impressions - actual_impressions
        if actual_impressions > 0:
            rev_per_imp = actual_revenue / actual_impressions
            rate_src = "observed revenue/impression in this window"
        else:
            rev_per_imp, rate_src = 0.0, "no impressions in window -- no observed rate"
        if rev_per_imp <= 0:
            return ImpactEstimate(0.0, "unavailable", {
                "reason": "no revenue-per-impression observable for this slice/window"})
        return ImpactEstimate(
            impact_usd=missing * rev_per_imp,
            basis="render-based (unshown impressions x observed revenue/impression)",
            detail={
                "unit": "impressions", "expected_units": expected_impressions,
                "actual_units": actual_impressions, "missing_units": missing,
                "revenue_per_unit": rev_per_imp, "rate_source": rate_src,
                "actual_fills": actual_fills, "seasonal_cell": band.seasonal_cell,
            },
        )

    # --- volume / engagement counts: price the shortfall at this slice's own
    #     revenue per unit of that count ---
    numerator = spec.numerator
    actual_units = float(measures.get(f"{prefix}_{numerator}") or 0)
    expected_units = band.center if spec.denominator is None else None
    if expected_units is None:
        # A ratio metric not handled above (ctr). Convert the rate move into a
        # count move on the volume that actually occurred.
        expected_units = band.center * actual_impressions
    missing = expected_units - actual_units

    # Clicks do not carry revenue in this data model, so a click shortfall must not be
    # priced as one. MEASURED, not assumed: revenue per impression is 0.002472 (CPC),
    # 0.002471 (CPI) and 0.002470 (CPM) -- identical to four significant figures, so even
    # CPC campaigns accrue revenue on impressions and `campaign_type` is a label that does
    # not change how money is earned. Per day, CPC's revenue/impression varies by 1.0% while
    # its revenue/click varies by 6.1%: the impression rate is the stable one because it is
    # the real one.
    #
    # What the old arithmetic produced: tier_3's CTR fell to 0.00833 against a 0.01055
    # centre on 2026-06-24 (-3.1 sigma, 503 clicks against 637 expected), and pricing the
    # 134 missing clicks at revenue/click booked **$39.73 of "exposure"** -- which ranked it
    # FIRST, above a genuine $24.42/day demand outage. That day tier_3 earned $149 on 60,398
    # impressions, a revenue/impression of 0.002467 against a 35-day median of 0.002462.
    # Revenue was untouched. The $39.73 was a number the data does not contain.
    #
    # Real revenue moves are still caught, because `revenue` and `ecpm` are separately
    # monitored metrics with their own bands -- a click-driven loss would breach THOSE and be
    # priced there. So the effect is that a pure engagement move is recorded, clustered,
    # signature-matched and visible, but gated out of the money-ranked alert queue, which is
    # the honest place for a movement that costs nothing.
    #
    # `engagement_carries_revenue` exists for the unseen dataset: if it turns out to monetise
    # per click, set it and this branch prices clicks again. Verify before flipping it with
    # the query above -- compare revenue/impression against revenue/click across
    # campaign_type and see which one is constant.
    if numerator == "clicks" and not settings.engagement_carries_revenue:
        return ImpactEstimate(0.0, ENGAGEMENT_ZERO_EXPOSURE_BASIS, {
            "reason": ENGAGEMENT_ZERO_EXPOSURE_REASON,
            "unit": numerator, "expected_units": expected_units,
            "actual_units": actual_units, "missing_units": missing,
            "seasonal_cell": band.seasonal_cell,
        })

    if actual_units > 0 and actual_revenue > 0:
        rev_per_unit = actual_revenue / actual_units
        rate_src = f"observed revenue/{numerator} in this window"
    else:
        return ImpactEstimate(0.0, "unavailable", {
            "reason": f"no revenue-per-{numerator} observable for this slice/window",
            "actual_units": actual_units, "expected_units": expected_units,
        })
    return ImpactEstimate(
        impact_usd=missing * rev_per_unit,
        basis=f"count-based (missing {numerator} x observed revenue/{numerator})",
        detail={
            "unit": numerator, "expected_units": expected_units, "actual_units": actual_units,
            "missing_units": missing, "revenue_per_unit": rev_per_unit, "rate_source": rate_src,
            "seasonal_cell": band.seasonal_cell,
        },
    )


def decompose_impact(verdicts: list) -> dict:
    """Splits a set of confirmed breaches into per-entity dollar contributions,
    so an incident can say "adv_0007 explains $38 of the $50" rather than only
    naming a total.

    Deliberately NOT built on rank.py's `share_of_total_delta`: that share is
    normalised by the NET SIGNED total delta, so when segments move in opposite
    directions the denominator collapses and individual shares exceed 100%.
    Absolute expected-minus-actual dollars per entity have no such failure mode
    and are additive, which is what an attribution needs to be.
    """
    total = sum(v.impact_usd for v in verdicts)
    parts = []
    for v in sorted(verdicts, key=lambda x: -abs(x.impact_usd)):
        parts.append({
            "scope_type": v.scope_type,
            "scope_value": v.scope_value,
            "metric": v.metric,
            "grain": v.grain,
            "impact_usd": v.impact_usd,
            # Share of the summed absolute impact, so it is bounded in [0, 1] even
            # when some entities moved the other way.
            "share_of_impact": (abs(v.impact_usd) / sum(abs(x.impact_usd) for x in verdicts))
            if any(x.impact_usd for x in verdicts) else 0.0,
            "basis": v.impact_basis,
        })
    return {"total_impact_usd": total, "parts": parts}
