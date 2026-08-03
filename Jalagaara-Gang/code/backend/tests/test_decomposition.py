"""Log-additive (LMDI) factor attribution over the revenue identity — pure, no DB."""
from rca import decomposition as dc


def test_contributions_sum_to_one_and_primary_is_fill_rate():
    # fill_rate collapses 0.82 -> 0.61; requests/ecpm ~flat -> fill_rate must dominate
    exp = {"requests": 1_000_000, "fills": 820_000, "impressions": 820_000, "revenue": 2574.8}
    obs = {"requests": 980_000, "fills": 597_800, "impressions": 597_800, "revenue": 1847.2}
    fd = dc.decompose_from_sums(obs, exp)
    assert fd.method == "log_additive"
    assert len(fd.factors) == 3
    assert fd.primary_factor == "fill_rate"
    assert abs(sum(f.contribution_pct for f in fd.factors) - 1.0) < 0.02  # LMDI is exact/additive
    fr = next(f for f in fd.factors if f.factor == "fill_rate")
    assert abs(fr.from_ - 0.82) < 1e-6 and abs(fr.to - 0.61) < 1e-6


def test_requests_drop_makes_requests_primary():
    exp = {"requests": 220_000, "fills": 172_600, "impressions": 169_000, "revenue": 419.0}
    obs = {"requests": 126_000, "fills": 98_900, "impressions": 96_900, "revenue": 234.0}
    fd = dc.decompose_from_sums(obs, exp)
    assert fd.primary_factor == "requests"


def test_offsetting_factors_stay_bounded():
    # requests up +4%, fill_rate down (traffic masks the collapse) -> revenue ~flat. Share-of-net
    # would explode (>1000%); the guard must report share-of-gross instead, so |pct| stays <= 1.
    exp = {"requests": 778_000, "fills": 610_800, "impressions": 598_000, "revenue": 1481.0}
    obs = {"requests": 809_000, "fills": 627_700, "impressions": 614_800, "revenue": 1532.0}
    fd = dc.decompose_from_sums(obs, exp)
    assert all(abs(f.contribution_pct) <= 1.01 for f in fd.factors)   # no >100% blow-up
    assert any(f.contribution_pct < 0 for f in fd.factors)            # fill_rate is a negative contributor
    assert fd.primary_factor == "requests"


def test_near_zero_revenue_delta_does_not_explode():
    # requests +4.4% vs fill_rate -4.4% -> revenue essentially flat -> contributions must not blow up
    exp = {"requests": 1000, "fills": 785, "impressions": 785, "revenue": 1.97035}
    obs = {"requests": 1044, "fills": 784, "impressions": 784, "revenue": 1.96784}
    fd = dc.decompose_from_sums(obs, exp)
    assert all(abs(f.contribution_pct) <= 1.01 for f in fd.factors)   # not thousands of percent
    assert fd.primary_factor == "fill_rate"
