"""Step 5: Rule out alternatives. Records dimensions/factors that did NOT
explain the deviation, with the actual numbers that clear them -- this is
what the problem statement calls "honest": showing what was checked and
cleared, not just what was found. The seasonality check always runs
unconditionally, since at least one planted anomaly in the sample data is
pure seasonality and must be checked and ruled out, not alarmed on.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from engine.baseline import BaselineResult, check_baseline
from engine.ch_client import ChClient, Trace
from engine.config import settings
from engine.decompose import DecomposeResult
from engine.rank import DimensionRanking


@dataclass
class RuledOutCheck:
    check: str
    reason: str
    numbers: dict


def rule_out_factors(decompose_result: DecomposeResult, threshold: Optional[float] = None) -> list:
    """Factors from the revenue decomposition whose |share| is small get
    explicitly recorded as ruled out, with their actual log-ratio numbers."""
    threshold = threshold if threshold is not None else 0.15  # a factor contributing <15% of the log-move is "normal"
    ruled_out = []
    for f in decompose_result.factors:
        if abs(f.share) < threshold:
            ruled_out.append(
                RuledOutCheck(
                    check=f"factor:{f.factor}",
                    reason=f"{f.factor} moved only marginally (now={f.now:.6g}, baseline={f.baseline:.6g}) and accounts for "
                    f"{f.share:.1%} of the deviation -- not the driver.",
                    numbers={"now": f.now, "baseline": f.baseline, "share": f.share},
                )
            )
    return ruled_out


def rule_out_dimensions(rankings: list, threshold: float = 0.15) -> list:
    """Dimensions whose top segment doesn't concentrate a meaningful share of
    the deviation are recorded as checked-and-cleared, not silently dropped."""
    ruled_out = []
    for ranking in rankings:
        top = ranking.top_segment
        if top is None or abs(top.share_of_total_delta) < threshold:
            ruled_out.append(
                RuledOutCheck(
                    check=f"dimension:{ranking.dimension}",
                    reason=f"No single {ranking.dimension} segment concentrates the deviation "
                    f"(top segment '{top.value if top else 'n/a'}' accounts for only "
                    f"{(top.share_of_total_delta if top else 0):.1%} of the delta) -- deviation is spread evenly, "
                    f"not localized to this dimension.",
                    numbers={"top_segment": top.value if top else None, "share": top.share_of_total_delta if top else 0.0},
                )
            )
    return ruled_out


def check_seasonality(client: ChClient, trace: Trace, window_start: datetime, window_end: datetime) -> RuledOutCheck:
    """Always-run check: does this window's request volume match the same
    weekday/hour-of-day pattern as recent weeks (a seasonal dip/rise), or is
    it genuinely off-pattern? Uses the same baseline machinery as step 1 but
    is recorded unconditionally, per CLAUDE.md's seasonality caveat."""
    result: BaselineResult = check_baseline(client, trace, "requests", window_start, window_end, trailing_weeks=settings.baseline_trailing_weeks)
    matches_seasonal_pattern = abs(result.zscore) < settings.rule_out_zscore_threshold

    if matches_seasonal_pattern:
        reason = (
            f"Request volume ({result.current_value:.0f}) is within normal range of the trailing "
            f"{settings.baseline_trailing_weeks}-week same-weekday/same-hour baseline "
            f"(mean={result.baseline_mean:.0f}, z={result.zscore:.2f}) -- this window's shape matches "
            f"expected day-of-week/hour-of-day seasonality, not an incident."
        )
    else:
        reason = (
            f"Request volume ({result.current_value:.0f}) deviates from the trailing "
            f"{settings.baseline_trailing_weeks}-week same-weekday/same-hour baseline "
            f"(mean={result.baseline_mean:.0f}, z={result.zscore:.2f}) beyond normal seasonal variation -- "
            f"seasonality alone does not explain this window."
        )

    return RuledOutCheck(
        check="seasonality",
        reason=reason,
        numbers={
            "current_requests": result.current_value,
            "baseline_mean_requests": result.baseline_mean,
            "baseline_stdev_requests": result.baseline_stdev,
            "zscore": result.zscore,
            "matches_seasonal_pattern": matches_seasonal_pattern,
        },
    )
