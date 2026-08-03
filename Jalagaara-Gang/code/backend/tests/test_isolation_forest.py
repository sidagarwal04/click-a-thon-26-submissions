"""IsolationForest detector: pure scoring over hand-built frames (no live DB)."""
from datetime import datetime, timedelta

import pandas as pd

from rca.detectors import isolation_forest as iforest

_PARAMS = {"n_estimators": 100, "contamination": "auto", "random_state": 42, "min_pct_delta": 0.05}


def _frame(spike_at: datetime | None = None, spike_val: float | None = None) -> pd.DataFrame:
    """~5 weeks hourly: seasonal by hour-of-day (100 + hod) with small week-to-week noise."""
    rows = []
    start = datetime(2026, 6, 1, 0)
    for day in range(35):
        for hod in range(24):
            t = start + timedelta(days=day, hours=hod)
            v = float(100 + hod + ((day % 3) - 1))
            if spike_at is not None and t == spike_at:
                v = float(spike_val)
            rows.append({"hour": t, "value": v})
    return pd.DataFrame(rows)


def test_univariate_flags_spike():
    target = datetime(2026, 6, 29, 10)
    df = _frame(spike_at=target, spike_val=600.0)
    a = iforest.score_frame(df, target, "univariate", [], _PARAMS)
    assert a.detected is True
    assert a.direction == "spike"
    assert a.expected == 110.0


def test_univariate_normal_not_flagged():
    target = datetime(2026, 6, 29, 10)
    a = iforest.score_frame(_frame(), target, "univariate", [], _PARAMS)
    assert a.detected is False


def test_multivariate_flags_weird_combo():
    target = datetime(2026, 6, 29, 10)
    df = _frame()
    # two stable feature columns; inject an outlier COMBINATION at the target hour
    df["ctr"] = 0.02 + ((df.index % 3) - 1) * 0.001
    df["ecpm"] = 1.5 + ((df.index % 3) - 1) * 0.01
    ti = df.index[df["hour"] == pd.Timestamp(target)][0]
    df.loc[ti, ["ctr", "ecpm"]] = [0.9, 40.0]
    a = iforest.score_frame(df, target, "multivariate", ["ctr", "ecpm"], _PARAMS)
    assert a.detected is True


def test_deterministic_with_fixed_seed():
    target = datetime(2026, 6, 29, 10)
    df = _frame(spike_at=target, spike_val=600.0)
    a1 = iforest.score_frame(df, target, "univariate", [], _PARAMS)
    a2 = iforest.score_frame(df, target, "univariate", [], _PARAMS)
    assert a1.score == a2.score
