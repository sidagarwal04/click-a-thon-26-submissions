"""Step 2: Decompose metric. Revenue ~= Requests x Fill rate x eCPM/1000
(Docs/metrics_glossary.md's decomposition identity). Walking this first tells
us which factor moved -- volume, fill, or price -- before slicing by
dimension, so rank.py/drilldown.py know which factor's deviation to localize
rather than guessing.
"""

import math
from dataclasses import dataclass, field

from engine.baseline import BaselineResult, WindowStats
from engine.config import REVENUE_DECOMPOSITION_FACTORS


@dataclass
class FactorContribution:
    factor: str
    now: float
    baseline: float
    log_ratio: float  # log(now/baseline); this factor's additive share of the revenue move in log space
    share: float  # this factor's share of the total revenue log-change (|share| sums to 1 across factors)
    degenerate: bool = False  # now or baseline was <= 0, so no log ratio exists for this factor


@dataclass
class DecomposeResult:
    revenue_now: float
    revenue_baseline: float
    factors: list  # list[FactorContribution], ordered by |share| descending
    primary_factor: str  # the factor with the largest |share|
    # How closely the factors actually reproduce the revenue move. With the full
    # 4-factor identity these should be equal to floating-point tolerance:
    #   requests x (fills/requests) x (impressions/fills) x (revenue/impressions)
    #     == revenue    -- exactly, by cancellation
    # so log(revenue_now/revenue_base) == sum of the four log-ratios.
    revenue_log_ratio: float = 0.0
    factors_log_sum: float = 0.0
    residual: float = 0.0
    identity_closes: bool = True
    # Set when a factor had to be dropped (a zero denominator somewhere). The
    # decomposition is then genuinely incomplete, and says so rather than
    # presenting shares that silently do not account for the move.
    degenerate_factors: list = field(default_factory=list)


# A residual this size or smaller is floating-point noise on an identity that
# cancels exactly. Anything larger means a factor is missing or a baseline was
# built inconsistently -- a real defect, and one worth surfacing rather than
# rounding away.
IDENTITY_TOLERANCE = 1e-6


def _safe_log_ratio(now: float, baseline: float) -> float:
    if now <= 0 or baseline <= 0:
        return 0.0
    return math.log(now / baseline)


def decompose_revenue(revenue_baseline_result: BaselineResult, factor_baselines: dict) -> DecomposeResult:
    """`factor_baselines` maps factor name -> BaselineResult for that factor
    (requests, fill_rate, render_rate, ecpm), each computed over the identical
    window by baseline.check_baseline().

    The identity is EXACT, not approximate:

        requests x (fills/requests) x (impressions/fills) x (revenue/impressions)
            == revenue

    every intermediate term cancels, so in log space the four factor log-ratios
    must sum to log(revenue_now / revenue_baseline). This function computes that
    residual and reports it rather than assuming it.

    That check is not ceremony. The previous 3-factor version
    (requests / fill_rate / ecpm) omitted render_rate, so any render movement was
    absorbed into the surviving factors and the shares looked complete while
    attributing the move to the wrong place. render_rate -- the "show rate" -- is
    exactly what breaks when an app's integration stops rendering (S7) or a
    format's player breaks (S11), so its omission also made those two mechanisms
    undiagnosable. A non-zero residual now means something is genuinely missing,
    and the caller is told.
    """
    contributions = []
    for factor in REVENUE_DECOMPOSITION_FACTORS:
        br = factor_baselines[factor]
        degenerate = not (br.current_value > 0 and br.baseline_mean > 0)
        contributions.append(
            FactorContribution(
                factor=factor,
                now=br.current_value,
                baseline=br.baseline_mean,
                log_ratio=_safe_log_ratio(br.current_value, br.baseline_mean),
                share=0.0,
                degenerate=degenerate,
            )
        )

    # |share| sums to 1 across factors, and share keeps its sign so direction
    # survives. Normalizing by the sum of ABSOLUTE log-ratios (rather than the
    # signed sum) is deliberate: when two factors move in opposite directions the
    # signed sum can approach zero and shares would explode.
    total_abs_log = sum(abs(c.log_ratio) for c in contributions) or 1.0
    for c in contributions:
        c.share = c.log_ratio / total_abs_log if total_abs_log else 0.0

    contributions.sort(key=lambda c: abs(c.share), reverse=True)

    revenue_log_ratio = _safe_log_ratio(
        revenue_baseline_result.current_value, revenue_baseline_result.baseline_mean
    )
    factors_log_sum = sum(c.log_ratio for c in contributions)
    degenerate_factors = [c.factor for c in contributions if c.degenerate]
    residual = revenue_log_ratio - factors_log_sum
    # A degenerate factor (zero impressions, zero fills, ...) legitimately has no
    # log ratio, so the identity cannot close and claiming otherwise would be the
    # false claim. Only a fully-defined decomposition is held to the tolerance.
    identity_closes = (not degenerate_factors) and abs(residual) <= IDENTITY_TOLERANCE

    return DecomposeResult(
        revenue_now=revenue_baseline_result.current_value,
        revenue_baseline=revenue_baseline_result.baseline_mean,
        factors=contributions,
        primary_factor=contributions[0].factor if contributions else "revenue",
        revenue_log_ratio=revenue_log_ratio,
        factors_log_sum=factors_log_sum,
        residual=residual,
        identity_closes=identity_closes,
        degenerate_factors=degenerate_factors,
    )
