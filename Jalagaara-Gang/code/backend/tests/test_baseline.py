"""Covers the baseline engine's pure logic (SQL shape, filters, stat build) without a live DB."""
from datetime import datetime

import pytest

from rca import baseline as b


def test_where_builds_parameterized_clause():
    sql, params = b._where({"country": "IN", "os_version": "Android 13"})
    assert "country = {seg0:String}" in sql and "os_version = {seg1:String}" in sql
    assert params == {"seg0": "IN", "seg1": "Android 13"}


def test_where_empty():
    assert b._where(None) == ("", {})


def test_where_rejects_unknown_column():
    with pytest.raises(ValueError):
        b._where({"evil; DROP": "x"})


def test_observed_and_baseline_sql_shape():
    obs = b._observed_sql("sum(revenue)", "")
    assert obs.startswith("SELECT sum(revenue) AS value FROM")
    obs_dim = b._observed_sql("sum(revenue)", "", "country")
    assert "country AS seg" in obs_dim and "GROUP BY country" in obs_dim
    base = b._baseline_sql("sum(revenue)", "")
    assert "toDayOfWeek(hour) = toDayOfWeek(toDateTime({target:String}))" in base
    assert "toHour(hour) = toHour(toDateTime({target:String}))" in base
    assert base.rstrip().endswith("GROUP BY hour")


def test_build_stat_detects_drop():
    # min_effect=0.05: a real, calibrated-style floor, passed in directly since _build_stat
    # is pure (no DB/metric lookup) — see rca/baseline.py's _detected docstring.
    stat = b._build_stat({"country": "IN"}, 76000, [90000, 91000, 89000, 90500], min_effect=0.05)
    assert stat.direction == "drop"
    assert stat.detected is True
    assert stat.n_baseline == 4


def test_build_stat_mad_zero_uses_pct_fallback():
    stat = b._build_stat({}, 60, [100, 100, 100], min_effect=0.1)  # mad 0 -> 40% drop trips min_effect
    assert stat.mad == 0.0
    assert stat.detected is True


def test_build_stat_normal_not_flagged():
    stat = b._build_stat({}, 90200, [90000, 91000, 89000, 90500], min_effect=0.05)
    assert stat.detected is False


def test_scan_rejects_unknown_dimension():
    with pytest.raises(ValueError):
        b.scan("revenue", datetime(2026, 7, 4, 10), "not_a_dimension")
