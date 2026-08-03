"""A statistically large move is not the same thing as a material one.

WHY THIS FILE EXISTS
At k = 3.0 the 35-day replay still raised on 21 of 29 quiet days. The residual source is
the one PROGRESS.md named and then excused: "z-scores on very low-variance ratio metrics
(like fill_rate) can run high in magnitude even for small absolute moves". That is not a
property of the data, it is a divide-by-near-zero.

A slice whose trailing history happens to be nearly flat gets a MAD near zero. Dividing a
move of a fraction of a percentage point by it produces a six-sigma verdict on a number
nobody would look at twice. The dollar gate does not catch these -- such a slice can be
worth well over $1/day, and `scripts/backtest.py` counts `alertable()` output, which is
already post-gate.

`evaluate()` therefore applies two floors, and these tests pin both plus the property that
matters more than either: **the floors must not cost a real detection.** The Android outage
is -17pp; anything that suppresses that is wrong regardless of how clean it makes the
false-positive table.

Both floors default to 0.0, so the unfloored behaviour is also pinned here -- otherwise a
future default change would silently alter every threshold's meaning.
"""

from datetime import datetime

import pytest

from engine.bands import METHOD_CONSTANT, METHOD_MEDIAN_MAD, Band, evaluate

WINDOW_START = datetime(2026, 6, 24)
WINDOW_END = datetime(2026, 6, 25)


def _band(center, spread, metric="fill_rate", method=METHOD_MEDIAN_MAD, denom_center=60000.0):
    return Band(
        scope_type="os_family", scope_value="Android", metric=metric, grain="1d",
        seasonal_cell="dow_hod:3|all", center=center, spread=spread,
        method=method, sample_count=20, denom_center=denom_center,
    )


def _eval(band, value, **kw):
    """Both floors default to OFF here, regardless of what the shipped config says.

    Not a convenience: a test that inherits `settings.min_relative_spread` is really
    testing today's adopted value, and silently changes meaning the next time the
    backtest moves it. Each test below states the floors it is exercising, so the
    arithmetic it pins stays pinned. (This bit for real — adopting a 2% default turned
    the effect-floor test into a spread-floor test, and it failed rather than quietly
    passing for the wrong reason.)
    """
    kw.setdefault("min_relative_spread", 0.0)
    kw.setdefault("min_relative_move", 0.0)
    return evaluate(band, value=value, denom=band.denom_center,
                    window_start=WINDOW_START, window_end=WINDOW_END, **kw)


# ---------------------------------------------------------------------------
# The defect, reproduced
# ---------------------------------------------------------------------------
def test_near_zero_mad_manufactures_a_six_sigma_move_from_nothing():
    """Unfloored, a 0.2% move on a nearly-flat slice reads as a huge breach.

    This is the false positive the floors exist to remove, pinned as a fact about the
    old behaviour so the fix is measured against something real rather than asserted.
    """
    band = _band(center=0.800, spread=0.00005)
    v = _eval(band, value=0.7984, min_relative_spread=0.0, min_relative_move=0.0)

    assert v.breached
    assert abs(v.deviation_score) > 30       # ~32 sigma
    assert abs(v.pct_change) < 0.003         # ...on a 0.2% move


def test_spread_floor_widens_the_band_and_the_move_stops_breaching():
    band = _band(center=0.800, spread=0.00005)
    v = _eval(band, value=0.7984, min_relative_spread=0.02)

    # The floor is 2% of the centre = 0.016, against the band's own 0.00005.
    assert v.spread_floored
    assert v.spread == 0.016
    assert v.band_spread == 0.00005          # the raw figure is kept, not overwritten
    assert abs(v.deviation_score) < 1.0
    assert not v.breached
    assert not v.suppressed                  # it simply did not cross; nothing to suppress


def test_spread_reported_is_the_spread_divided_by():
    """`(value - center) / spread` must reproduce the score by hand.

    A verdict whose printed spread is not the one used in the arithmetic cannot be
    checked, and an unverifiable number is the thing the guardrails exist to prevent.
    """
    band = _band(center=0.800, spread=0.00005)
    v = _eval(band, value=0.7984, min_relative_spread=0.02)

    assert v.deviation_score == (v.value - v.center) / v.spread
    assert v.as_reason().find(f"{v.spread:.6g}") != -1


# ---------------------------------------------------------------------------
# The effect floor is a second, independent argument
# ---------------------------------------------------------------------------
def test_effect_floor_suppresses_a_genuine_sigma_breach_that_is_immaterial():
    """Wide-enough band, real 4-sigma crossing, but the move is 0.5%."""
    band = _band(center=0.800, spread=0.001)
    v = _eval(band, value=0.796, min_relative_spread=0.0, min_relative_move=0.02)

    assert abs(v.deviation_score) >= 4.0     # it really did cross
    assert v.suppressed
    assert not v.breached
    assert v.severity == ""
    assert v.direction == "none"


def test_suppressed_is_not_skipped_and_carries_its_numbers():
    """Suppression is a verdict; absence is not.

    sweep.py routes `skipped` into skipped_no_band / skipped_low_power and OUT of
    entities_evaluated. A cell that was evaluated and found immaterial was still
    evaluated, so marking it skipped would understate coverage -- and a coverage grid
    that quietly shrinks is the same class of error as reporting "0 suppressed" while
    791 were.
    """
    band = _band(center=0.800, spread=0.001)
    v = _eval(band, value=0.796, min_relative_move=0.02)

    assert v.suppressed
    assert not v.skipped
    assert v.skip_reason == ""
    assert "0.50%" in v.suppress_reason      # the move
    assert "2.00% effect floor" in v.suppress_reason
    assert v.as_reason() == v.suppress_reason


def test_the_two_floors_are_independent():
    """A move can fail one and pass the other, in both directions.

    If the effect floor were merely a stricter spread floor there would be no case
    where the spread floor binds and the effect floor does not, nor the reverse.
    """
    # Spread floor binds (tight band), effect floor passes (big move).
    tight = _band(center=0.800, spread=0.00005)
    v1 = _eval(tight, value=0.640, min_relative_spread=0.02, min_relative_move=0.02)
    assert v1.spread_floored and v1.breached and not v1.suppressed

    # Spread floor does not bind (wide band), effect floor catches it (small move).
    wide = _band(center=0.800, spread=0.001)
    v2 = _eval(wide, value=0.796, min_relative_spread=0.0005, min_relative_move=0.02)
    assert not v2.spread_floored and v2.suppressed


# ---------------------------------------------------------------------------
# The property that outranks all of the above
# ---------------------------------------------------------------------------
def test_the_android_outage_still_breaches_with_both_floors_active():
    """INC-0623: os_family=Android fill rate, -17.1pp on a 0.80 centre.

    A 21% relative move against a 2% effect floor and a 2% spread floor. If any floor
    setting suppresses this, that setting is rejected -- the backtest's acceptance gate
    is the detection date, never the false-positive count.
    """
    band = _band(center=0.800, spread=0.004)
    v = _eval(band, value=0.629, min_relative_spread=0.02, min_relative_move=0.02)

    assert v.breached
    assert v.direction == "below"
    assert not v.suppressed
    assert abs(v.pct_change) > 0.20


def test_a_material_move_on_a_flat_slice_survives_the_spread_floor():
    """The floor must remove noise, not blind the system to a collapse.

    Same near-zero-MAD slice as the defect test, but the value actually falls off a
    cliff. Under the floor it is 10 sigma instead of 3,200 -- still, correctly, a breach.
    """
    band = _band(center=0.800, spread=0.00005)
    v = _eval(band, value=0.640, min_relative_spread=0.02, min_relative_move=0.02)

    assert v.spread_floored
    assert v.breached
    assert abs(v.deviation_score) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Defaults, and the edges
# ---------------------------------------------------------------------------
def test_zero_floors_reproduce_the_unfloored_arithmetic_exactly():
    band = _band(center=0.800, spread=0.004)
    v = _eval(band, value=0.780, min_relative_spread=0.0, min_relative_move=0.0)

    assert not v.spread_floored
    assert v.spread == band.spread
    assert v.deviation_score == (0.780 - 0.800) / 0.004
    assert v.breached


def test_a_zero_centre_has_no_relative_scale_so_neither_floor_applies():
    """|centre| = 0 makes both floors degenerate: the spread floor is 0 and there is no
    percentage to compare against. Neither may fabricate a suppression."""
    band = _band(center=0.0, spread=0.5, metric="clicks", denom_center=60000.0)
    v = _eval(band, value=3.0, min_relative_spread=0.02, min_relative_move=0.02)

    assert v.pct_change is None
    assert not v.spread_floored
    assert not v.suppressed
    assert v.breached


def test_the_shipped_defaults_are_the_backtested_ones():
    """Pins what actually runs, not just what the arithmetic can do.

    Every other test here passes its floors explicitly, which is correct for testing the
    mechanism and useless for catching a config edit. These two values came out of a
    35-day replay (Docs/BACKTEST_SCORECARD.md); changing either means re-running it, so
    changing either should break a test rather than quietly change the detector.
    """
    from engine.config import settings

    assert settings.min_relative_spread == 0.02
    # Measured as contributing nothing once the spread floor is present, so shipped off.
    assert settings.min_relative_move == 0.0
    # The consequence a reader actually needs: k x floor is the smallest relative move
    # that can ever breach. At the adopted values that is 6%.
    assert settings.band_k_amber * settings.min_relative_spread == pytest.approx(0.06)


def test_the_android_outage_survives_the_shipped_defaults():
    """The adopted floor, applied to the real incident, with no arguments passed."""
    band = _band(center=0.800, spread=0.004)
    v = evaluate(band, value=0.629, denom=band.denom_center,
                 window_start=WINDOW_START, window_end=WINDOW_END)

    assert v.breached and not v.suppressed
    assert v.direction == "below"


def test_constant_history_is_floored_rather_than_scored_as_the_sentinel():
    """A metric that never varied gets spread 0 and a +/-100 sentinel. That sentinel is
    exactly the divide-by-nothing the floor exists to replace, so when a floor is
    configured it takes precedence -- and the sentinel still applies when it is not."""
    band = _band(center=0.800, spread=0.0, method=METHOD_CONSTANT)

    unfloored = _eval(band, value=0.7984, min_relative_spread=0.0)
    assert abs(unfloored.deviation_score) == 100.0

    floored = _eval(band, value=0.7984, min_relative_spread=0.02)
    assert floored.spread == 0.016
    assert abs(floored.deviation_score) < 1.0
    assert not floored.breached
