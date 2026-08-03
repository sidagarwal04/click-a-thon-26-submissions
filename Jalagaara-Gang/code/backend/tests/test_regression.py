"""JAL-77: localisation regression on four planted anomalies with ground truth.

Asserts the EXACT localized_segment (not just 'something detected'), covering the false-positive
guard (uniform global drop -> no segment) and a two-dimension interaction that single-dim scans miss.
Runs against live ClickHouse; skipped if unreachable.
"""
from datetime import datetime

import pytest

from config import config
from models import Window
from rca import drilldown

try:
    from data.client import run_query
    run_query("SELECT 1")
    _DB_UP = True
except Exception:  # noqa: BLE001
    _DB_UP = False

pytestmark = pytest.mark.skipif(not _DB_UP, reason="needs live ClickHouse")


def _win(start: str, end: str) -> Window:
    return Window(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end))


# (id, metric, anomaly window, expected localized_segment)
CASES = [
    ("A", "fill_rate", _win("2026-06-23", "2026-06-26"), {"os_version": "Android 15"}),
    ("B", "ecpm",      _win("2026-06-19", "2026-06-23"), {"category": "finance"}),
    ("C", "requests",  _win("2026-06-21", "2026-06-22"), {}),  # uniform global drop -> NO segment
    ("D", "fill_rate", _win("2026-06-28", "2026-07-01"), {"region": "APAC", "os_version": "iOS 18.1"}),
]


@pytest.mark.parametrize("cid,metric,window,expected", CASES, ids=[c[0] for c in CASES])
def test_localizes_exact_segment(cid, metric, window, expected):
    _, localized, queries = drilldown.drill(metric, metric, window, drilldown.baseline_window(window))
    assert localized == expected
    assert queries, "every localisation must be backed by logged SQL"


def test_broken_stop_criterion_makes_a_case_fail(monkeypatch):
    """Teeth: an over-permissive stop threshold over-localises finance (B) — proving the suite
    actually catches a regression in the drill-down, not just that it runs."""
    monkeypatch.setitem(config()["rca"], "stop_contribution_threshold", 0.15)
    window = _win("2026-06-19", "2026-06-23")
    _, localized, _ = drilldown.drill("ecpm", "ecpm", window, drilldown.baseline_window(window))
    assert localized != {"category": "finance"}
