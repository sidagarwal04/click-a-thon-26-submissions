"""Locks the robust-stat primitives used by the baseline engine."""
from rca.robust import mad, med, pct_delta, robust_z


def test_med():
    assert med([1, 2, 3]) == 2
    assert med([]) == 0.0


def test_mad():
    assert mad([1, 1, 1]) == 0.0
    assert mad([1, 2, 3, 4, 5]) == 1.0  # center 3, deviations [2,1,0,1,2] -> median 1


def test_robust_z_applies_scale():
    # denom = mad_value * scale = 5 * 2 = 10; (110 - 100) / 10 = 1.0
    assert robust_z(110, 100, 5, 2) == 1.0


def test_robust_z_degenerate_returns_zero():
    assert robust_z(60, 100, 0, 1.4826) == 0.0


def test_robust_z_flags_drop():
    assert robust_z(60, 100, 10, 1.4826) < 0


def test_pct_delta():
    assert pct_delta(76, 100) == -0.24
    assert pct_delta(5, 0) == 0.0
