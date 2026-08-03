"""Seasonal-ML detector: pure residual scoring over a hand-built hourly series (no live DB)."""
from datetime import datetime, timedelta

from rca.detectors import seasonal_ml

_SCALE, _Z, _PCT = 1.4826, 3.5, 0.05


def _series(weeks: int = 5, spike_at: datetime | None = None, spike_val: float | None = None):
    """Hourly series: seasonal by hour-of-day (100 + hod) with small week-to-week noise."""
    hours: list[datetime] = []
    values: list[float] = []
    start = datetime(2026, 6, 1, 0)
    for day in range(weeks * 7):
        for hod in range(24):
            t = start + timedelta(days=day, hours=hod)
            v = float(100 + hod + ((day % 3) - 1))  # noise in {-1, 0, 1} -> residual spread > 0
            if spike_at is not None and t == spike_at:
                v = float(spike_val)
            hours.append(t)
            values.append(v)
    return hours, values


def test_expected_is_weekday_hour_median():
    hours, values = _series()
    a = seasonal_ml.score_series(hours, values, datetime(2026, 6, 29, 10), _SCALE, _Z, _PCT)
    assert a.expected == 110.0  # 100 + hod(10); median over the (Mon, 10:00) cell


def test_flags_injected_spike():
    target = datetime(2026, 6, 29, 10)
    hours, values = _series(spike_at=target, spike_val=200.0)
    a = seasonal_ml.score_series(hours, values, target, _SCALE, _Z, _PCT)
    assert a.detected is True
    assert a.direction == "spike"
    assert a.observed == 200.0
    assert a.expected == 110.0
    assert a.score > _Z


def test_normal_hour_not_flagged():
    target = datetime(2026, 6, 29, 10)
    hours, values = _series()
    a = seasonal_ml.score_series(hours, values, target, _SCALE, _Z, _PCT)
    assert a.detected is False
