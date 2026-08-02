"""Regression test for a real bug found via load-testing the API: a window at
the very start of the dataset has zero trailing-week baseline history, which
used to produce an Infinity z-score (not valid JSON, and a misleading
is_anomalous=True with no real evidence behind it). Fixed in engine/baseline.py
to report insufficient_baseline=True and is_anomalous=False instead.
"""

from datetime import datetime

import pytest

from engine.baseline import check_baseline
from engine.ch_client import Trace, get_client


@pytest.mark.integration
def test_window_with_no_baseline_history_does_not_claim_anomaly():
    client = get_client()
    trace = Trace()

    # 2026-06-01 is the first day in the dataset -- no trailing week has any data.
    result = check_baseline(client, trace, "revenue", datetime(2026, 6, 1), datetime(2026, 6, 1, 1))

    assert result.baseline_sample_count == 0
    assert result.insufficient_baseline is True
    assert result.is_anomalous is False  # must never claim anomaly with zero baseline samples
    assert result.zscore == 0.0  # finite, JSON-safe
    assert result.pct_change is None  # honest "undefined", not a fabricated number
