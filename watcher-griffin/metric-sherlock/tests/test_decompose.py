"""Pure-function tests for engine/decompose.py's contribution math -- no
ClickHouse needed. This is exactly the kind of math that could silently
break trustworthiness if it regressed, per CLAUDE.md's "tested, not just
demoed" principle.

The decomposition now walks the FULL revenue identity, including render_rate
(the "show rate"):

    requests x (fills/requests) x (impressions/fills) x (revenue/impressions)
        == revenue

Every intermediate term cancels, so this holds exactly, and the tests below
hold it to that standard rather than to "approximately". The three-factor
version this replaced omitted render_rate and therefore silently folded any
render movement into the other factors -- which both misattributed the cause and
made a render bug (S7 for one app, S11 for one format) impossible to name.
"""

import math
from datetime import datetime

import pytest

from engine.baseline import BaselineResult, WindowStats
from engine.decompose import decompose_revenue


def _baseline_result(metric: str, current_value: float, baseline_mean: float) -> BaselineResult:
    window = WindowStats(datetime(2026, 6, 1), datetime(2026, 6, 2), 0, 0, 0, 0, 0.0)
    return BaselineResult(
        metric=metric,
        window=window,
        baseline_windows=[],
        baseline_mean=baseline_mean,
        baseline_stdev=0.0,
        baseline_sample_count=4,
        current_value=current_value,
        zscore=0.0,
        pct_change=(current_value - baseline_mean) / baseline_mean if baseline_mean else None,
        is_anomalous=False,
        insufficient_baseline=False,
    )


def _factors(requests, fill_rate, render_rate, ecpm):
    """Builds the four factor baselines from (now, baseline) pairs."""
    return {
        "requests": _baseline_result("requests", *requests),
        "fill_rate": _baseline_result("fill_rate", *fill_rate),
        "render_rate": _baseline_result("render_rate", *render_rate),
        "ecpm": _baseline_result("ecpm", *ecpm),
    }


def _revenue_from(requests, fill_rate, render_rate, ecpm):
    """Revenue implied by the identity, so a test's inputs are guaranteed
    self-consistent instead of hand-rounded into a residual."""
    return requests * fill_rate * render_rate * ecpm / 1000.0


def test_requests_drop_is_identified_as_primary_factor():
    now = (8000.0, 0.80, 0.98, 2.0)  # requests -20%, everything else flat
    base = (10000.0, 0.80, 0.98, 2.0)
    revenue = _baseline_result("revenue", _revenue_from(*now), _revenue_from(*base))
    factors = _factors(
        (now[0], base[0]), (now[1], base[1]), (now[2], base[2]), (now[3], base[3])
    )

    result = decompose_revenue(revenue, factors)

    assert result.primary_factor == "requests"
    shares = {f.factor: f.share for f in result.factors}
    assert abs(shares["requests"]) > abs(shares["fill_rate"])
    assert abs(shares["requests"]) > abs(shares["ecpm"])
    assert abs(shares["requests"]) > abs(shares["render_rate"])
    # unchanged factors contribute exactly 0 log-ratio -- not "about 0"
    assert shares["fill_rate"] == 0.0
    assert shares["render_rate"] == 0.0
    assert shares["ecpm"] == 0.0


def test_fill_rate_drop_is_identified_as_primary_factor():
    now = (10000.0, 0.72, 0.98, 2.0)  # fill_rate -10%
    base = (10000.0, 0.80, 0.98, 2.0)
    revenue = _baseline_result("revenue", _revenue_from(*now), _revenue_from(*base))
    factors = _factors((now[0], base[0]), (now[1], base[1]), (now[2], base[2]), (now[3], base[3]))

    result = decompose_revenue(revenue, factors)

    assert result.primary_factor == "fill_rate"


def test_render_rate_drop_is_identified_as_primary_factor():
    """The case the three-factor decomposition could not express at all: fills
    are normal, impressions are not. This is a render bug -- an owner and a fix
    entirely different from a demand shortfall -- and before render_rate was a
    factor it was silently attributed to eCPM."""
    now = (10000.0, 0.80, 0.76, 2.0)  # render_rate -22%, i.e. ads bought but not shown
    base = (10000.0, 0.80, 0.98, 2.0)
    revenue = _baseline_result("revenue", _revenue_from(*now), _revenue_from(*base))
    factors = _factors((now[0], base[0]), (now[1], base[1]), (now[2], base[2]), (now[3], base[3]))

    result = decompose_revenue(revenue, factors)

    assert result.primary_factor == "render_rate"
    shares = {f.factor: f.share for f in result.factors}
    assert shares["render_rate"] < 0  # it fell
    assert shares["ecpm"] == 0.0  # and eCPM is NOT blamed for it


def test_factor_shares_are_signed_and_reflect_direction():
    now = (10000.0, 0.80, 0.98, 2.4)  # ecpm +20%, the only mover
    base = (10000.0, 0.80, 0.98, 2.0)
    revenue = _baseline_result("revenue", _revenue_from(*now), _revenue_from(*base))
    factors = _factors((now[0], base[0]), (now[1], base[1]), (now[2], base[2]), (now[3], base[3]))

    result = decompose_revenue(revenue, factors)

    ecpm_share = next(f.share for f in result.factors if f.factor == "ecpm")
    assert ecpm_share > 0  # ecpm rose, and it's the only mover -> positive share
    assert result.primary_factor == "ecpm"


def test_identity_closes_exactly_when_all_four_factors_move():
    """The point of including render_rate: with all four factors present the
    decomposition is not an approximation, and the residual must be
    floating-point noise rather than "small enough"."""
    now = (8500.0, 0.74, 0.93, 2.35)
    base = (10000.0, 0.80, 0.98, 2.00)
    revenue = _baseline_result("revenue", _revenue_from(*now), _revenue_from(*base))
    factors = _factors((now[0], base[0]), (now[1], base[1]), (now[2], base[2]), (now[3], base[3]))

    result = decompose_revenue(revenue, factors)

    assert result.identity_closes is True
    assert result.residual == pytest.approx(0.0, abs=1e-9)
    assert result.factors_log_sum == pytest.approx(result.revenue_log_ratio, abs=1e-9)
    # |share| sums to 1 across the four factors, and each share keeps its sign.
    assert sum(abs(f.share) for f in result.factors) == pytest.approx(1.0)
    assert result.degenerate_factors == []


def test_identity_does_not_claim_to_close_when_a_factor_is_degenerate():
    """A zero denominator means a factor genuinely has no log-ratio, so the
    identity cannot close. Reporting identity_closes=True here would be a false
    claim; the decomposition must admit it is incomplete instead."""
    revenue = _baseline_result("revenue", 0.0, 1000.0)
    factors = _factors((10000.0, 10000.0), (0.0, 0.80), (0.0, 0.98), (0.0, 2.0))

    result = decompose_revenue(revenue, factors)

    assert result.identity_closes is False
    assert set(result.degenerate_factors) == {"fill_rate", "render_rate", "ecpm"}


def test_log_sum_equals_revenue_log_ratio_by_construction():
    """Sanity anchor on the algebra itself, independent of the implementation:
    log(a*b*c*d) == log a + log b + log c + log d."""
    now = (9000.0, 0.70, 0.95, 1.80)
    base = (10000.0, 0.80, 0.98, 2.00)
    expected = math.log(_revenue_from(*now) / _revenue_from(*base))
    got = sum(math.log(n / b) for n, b in zip(now, base))
    assert got == pytest.approx(expected, abs=1e-12)
