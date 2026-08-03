"""/dev admin dashboard — endpoint logic with the DB patched (no live ClickHouse)."""
import copy
from unittest.mock import patch

import pytest

from api import dev
from config import config
from models import Anomaly


def _fake_run_query(count=42):
    def fn(sql, params=None):
        s = sql.strip()
        if s == "SHOW TABLES":
            return {"rows": [["ad_events"], ["hourly_summary"]], "columns": ["name"]}
        if s.startswith("SELECT count()"):
            return {"rows": [[count]], "columns": ["count()"]}
        if s.startswith("SELECT *"):
            return {"rows": [[1, 2]], "columns": ["a", "b"], "resolved_sql": s}
        raise AssertionError(f"unexpected sql: {sql}")
    return fn


def test_list_tables_returns_names_and_counts():
    with patch.object(dev, "run_query", _fake_run_query(9)):
        out = dev.list_tables()
    assert out == [{"name": "ad_events", "rows": 9}, {"name": "hourly_summary", "rows": 9}]


def test_preview_rejects_unknown_table():
    with patch.object(dev, "run_query", _fake_run_query()):
        with pytest.raises(ValueError):
            dev.preview_table("bobby_drop", limit=5)


def test_preview_returns_columns_and_rows():
    with patch.object(dev, "run_query", _fake_run_query()):
        out = dev.preview_table("ad_events", limit=5)
    assert out["columns"] == ["a", "b"]
    assert out["rows"] == [[1, 2]]


def test_drop_requires_matching_confirm():
    with patch.object(dev, "run_query", _fake_run_query()):
        with pytest.raises(ValueError):
            dev.drop_table("ad_events", confirm="wrong")


def test_drop_executes_on_matching_confirm():
    calls = {}

    class FakeClient:
        def command(self, sql, parameters=None):
            calls["sql"] = sql

    with patch.object(dev, "run_query", _fake_run_query()), patch.object(dev, "get_client", lambda: FakeClient()):
        out = dev.drop_table("ad_events", confirm="ad_events")
    assert out == {"dropped": "ad_events"}
    assert "DROP TABLE" in calls["sql"]


def test_detect_applies_override_then_restores_config():
    seen = {}

    def fake_detect(metric, window):
        seen["method"] = config()["detection"]["method"]
        seen["thr"] = config()["detection"]["mad_z_threshold"]
        return Anomaly(detected=True, observed=1, expected=1, abs_delta=0, pct_delta=0, score=0, direction="spike"), []

    before = copy.deepcopy(config()["detection"])
    with patch.object(dev, "detect", fake_detect):
        out = dev.run_detect("revenue", "2026-07-04T10:00", method="seasonal_ml", overrides={"mad_z_threshold": 9.9})
    assert seen["method"] == "seasonal_ml"          # override active during the run
    assert seen["thr"] == 9.9
    assert config()["detection"] == before          # ...and fully restored afterward
    assert out["anomaly"]["detected"] is True


def test_detect_deep_merges_nested_override_and_restores():
    seen = {}

    def fake_detect(metric, window):
        d = config()["detection"]["isolation_forest"]
        seen["features"] = d["features"]
        seen["n_estimators"] = d["n_estimators"]  # sibling key must survive the nested override
        return Anomaly(detected=False, observed=1, expected=1, abs_delta=0, pct_delta=0, score=0, direction="spike"), []

    before = copy.deepcopy(config()["detection"])
    with patch.object(dev, "detect", fake_detect):
        dev.run_detect("revenue", "2026-07-04T10:00", method="isolation_forest",
                       overrides={"isolation_forest": {"features": "multivariate"}})
    assert seen["features"] == "multivariate"    # nested override applied
    assert seen["n_estimators"] == 200           # ...without clobbering siblings (deep merge)
    assert config()["detection"] == before       # fully restored


def test_benchmark_cases_cover_the_known_ground_truth():
    cases = dev.benchmark_cases()
    ids = {c["id"] for c in cases}
    # The four confirmed planted anomalies. Asserted as a SUBSET, not equality, so adding a
    # new verified case (e.g. E, the eCPM redistribution negative case) doesn't fail the suite.
    assert {"A", "B", "C", "D"} <= ids
    assert all({"id", "metric", "window", "expect_segment"} <= set(c) for c in cases)


def test_score_kind_differs_per_method():
    assert dev._score_kind("robust_z") != dev._score_kind("isolation_forest")
    assert "forest" in dev._score_kind("isolation_forest").lower() or "IF" in dev._score_kind("isolation_forest")


def test_sample_hours_spread_across_window():
    from datetime import datetime
    from models import Window
    hrs = dev._sample_hours(Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 26)), 3)
    assert len(hrs) == 3 and len(set(hrs)) == 3
    assert all(datetime(2026, 6, 23) <= h < datetime(2026, 6, 26) for h in hrs)


def test_run_detect_reports_score_kind():
    def fake_detect(metric, window):
        return Anomaly(detected=False, observed=1, expected=1, abs_delta=0, pct_delta=0, score=0, direction="spike"), []

    with patch.object(dev, "detect", fake_detect):
        r = dev.run_detect("revenue", "2026-07-04T10:00", method="isolation_forest")
    assert "score_kind" in r


def test_run_engine_benchmark_summarizes_each_bundle():
    from types import SimpleNamespace

    def fake_build_bundle(metric, window):
        return SimpleNamespace(
            anomaly=SimpleNamespace(detected=True, score=1.234),
            factor_decomposition=SimpleNamespace(primary_factor="fill_rate"),
            localized_segment={"os_version": "Android 15"},
            ruled_out=[SimpleNamespace(hypothesis="ecpm_price")],
            queries=[1, 2, 3, 4, 5],
        )

    with patch.object(dev, "build_bundle", fake_build_bundle):
        rows = dev.run_engine_benchmark()
    assert len(rows) == len(dev.benchmark_cases())   # one row per ground-truth case (not hardcoded)
    a = next(r for r in rows if r["id"] == "A")
    assert a["primary_factor"] == "fill_rate"
    assert a["localized"] == {"os_version": "Android 15"}
    assert a["hit"] is True                       # matches case A ground truth
    assert a["ruled_out"] == ["ecpm_price"]
    assert a["n_queries"] == 5
    assert "start" in a and "end" in a           # so the row can be clicked to view its bundle
    assert next(r for r in rows if r["id"] == "B")["hit"] is False


def test_full_bundle_serializes_the_built_bundle():
    class FakeBundle:
        def model_dump(self, **kwargs):
            return {"metric": "revenue", "anomaly": {"detected": True}}

    with patch.object(dev, "build_bundle", lambda metric, window: FakeBundle()):
        out = dev.full_bundle("revenue", "2026-06-21", "2026-06-22")
    assert out == {"metric": "revenue", "anomaly": {"detected": True}}


def test_run_mega_produces_rows_and_summary():
    def fake_run_detect(metric, at, method=None, overrides=None, segment_aware=False):
        return {"method": method or "robust_z", "anomaly": {"detected": True, "score": 0.5},
                "queries": [], "found_in_segment": {}}

    def fake_drill(metric, factor, target, baseline):
        return [], {"os_version": "Android 15"}, []

    with patch.object(dev, "run_detect", fake_run_detect), patch.object(dev.drilldown, "drill", fake_drill):
        res = dev.run_mega(hours_per_case=2)
    n = len(dev._MEGA_METHODS)
    assert len(res["rows"]) == n * len(dev.benchmark_cases())   # every variant x every case
    assert len(res["summary"]) == n
    assert all("detection_rate" in s for s in res["summary"])


def test_case_window_parses_range_and_single_day():
    r = dev._case_window("2026-06-23..25")
    assert (r.start.isoformat(), r.end.isoformat()) == ("2026-06-23T00:00:00", "2026-06-26T00:00:00")
    s = dev._case_window("2026-06-21")
    assert (s.start.isoformat(), s.end.isoformat()) == ("2026-06-21T00:00:00", "2026-06-22T00:00:00")


def test_run_benchmark_includes_localization_and_hit():
    def fake_run_detect(metric, at, method=None, overrides=None, segment_aware=False):
        return {"method": method or "robust_z", "score_kind": "z", "anomaly": {"detected": True, "score": 1.0},
                "queries": [], "found_in_segment": {}}

    def fake_drill(metric, factor, target, baseline):
        return [], {"os_version": "Android 15"}, []  # matches case A's ground truth only

    with patch.object(dev, "run_detect", fake_run_detect), patch.object(dev.drilldown, "drill", fake_drill):
        rows = dev.run_benchmark()
    assert all("localized" in r and "hit" in r for r in rows)
    row_a = next(r for r in rows if r["id"] == "A")
    assert row_a["localized"] == {"os_version": "Android 15"}
    assert row_a["hit"] is True
    assert next(r for r in rows if r["id"] == "B")["hit"] is False


def test_run_benchmark_forwards_method_and_overrides():
    seen = []

    def fake_run_detect(metric, at, method=None, overrides=None, segment_aware=False):
        seen.append((metric, method, overrides, segment_aware))
        return {"method": method or "robust_z", "score_kind": "z", "anomaly": {"detected": True, "score": 1.0},
                "queries": [], "found_in_segment": {}}

    with patch.object(dev, "run_detect", fake_run_detect):
        rows = dev.run_benchmark(method="seasonal_ml", overrides={"min_pct_delta": 0.2})
    assert len(seen) == len(dev.benchmark_cases())               # every case runs
    assert all(m == "seasonal_ml" for _, m, _, _ in seen)        # chosen method forwarded
    assert all(o == {"min_pct_delta": 0.2} for _, _, o, _ in seen)  # overrides forwarded
    assert all(sa is True for *_, sa in seen)                    # benchmark must run segment-aware
    assert all(r["method"] == "seasonal_ml" for r in rows)       # and reported back per row


def test_dev_enabled_default_on_and_off(monkeypatch):
    monkeypatch.delenv("ENABLE_DEV_DASHBOARD", raising=False)
    assert dev.dev_enabled() is True
    monkeypatch.setenv("ENABLE_DEV_DASHBOARD", "0")
    assert dev.dev_enabled() is False
