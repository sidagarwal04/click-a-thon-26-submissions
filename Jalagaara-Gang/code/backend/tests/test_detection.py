"""Detection dispatch + robust_z detector mapping — pure logic, no live DB."""
import pytest

from models import Anomaly
from rca import detection
from rca.baseline import Stat


def _stat(**kw) -> Stat:
    base = dict(
        segment={}, observed=76.0, expected=100.0, mad=10.0, robust_z=-2.4,
        pct_delta=-0.24, direction="drop", detected=True, n_baseline=3,
    )
    base.update(kw)
    return Stat(**base)


def test_to_anomaly_maps_stat_fields():
    from rca.detectors import robust_z
    a = robust_z.to_anomaly(_stat())
    assert isinstance(a, Anomaly)
    assert a.observed == 76.0
    assert a.expected == 100.0
    assert a.abs_delta == -24.0
    assert a.pct_delta == -0.24
    assert a.score == -2.4
    assert a.direction == "drop"
    assert a.detected is True


def test_select_returns_robust_z_runner():
    from rca.detectors import robust_z
    assert detection._select("robust_z") is robust_z.run


def test_select_returns_seasonal_ml_runner():
    from rca.detectors import seasonal_ml
    assert detection._select("seasonal_ml") is seasonal_ml.run


def test_select_returns_isolation_forest_runner():
    from rca.detectors import isolation_forest
    assert detection._select("isolation_forest") is isolation_forest.run


def test_select_unknown_method_raises():
    with pytest.raises(ValueError):
        detection._select("not_a_method")
