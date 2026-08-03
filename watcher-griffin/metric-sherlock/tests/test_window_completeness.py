"""The evaluation window must lie entirely inside the available data.

WHY THIS FILE EXISTS
This guard was added after a measured 200x false-breach explosion, and the failure is worth
stating because it looks nothing like a bug from the outside:

    sweeping as_of = 2026-06-02 against data that starts 2026-06-01 produced
    67,360 confirmed breaches, of which 67,159 were on grains coarser than 1d
    and EVERY one was direction='below'.

Nothing was wrong with the bands or the thresholds. A 5-day window ending Jun 2 spans
May 28..Jun 2, but only Jun 1..Jun 2 has data -- so the window sums one day of traffic and is
compared against a band built from five-day windows. Every scope and every metric reads ~80%
low, simultaneously, and it presents as a catastrophic platform-wide outage.

The 1d and finer grains, whose windows were fully inside the data, produced 201 breaches on
the same day -- an ordinary day. That contrast is what identifies it as arithmetic rather than
anomaly.

This matters far beyond the backtest that found it: it would fire on the first three weeks
against ANY new dataset, and again after any ingestion gap.
"""

from datetime import datetime

import pytest

from engine import sweep
from engine.grains import GRAIN_REGISTRY


@pytest.fixture(autouse=True)
def _clear_floor_cache():
    """data_floor caches for the process; each test sets its own floor."""
    sweep._DATA_FLOOR.clear()
    yield
    sweep._DATA_FLOOR.clear()


class _FakeClient:
    def __init__(self, floor):
        self.floor = floor
        self.queries = 0

    def query(self, sql, step=None, trace=None):
        self.queries += 1
        if "min(event_time)" in sql:
            return [{"lo": self.floor}]
        raise AssertionError(f"unexpected query in this test: {sql[:80]}")


def test_data_floor_is_read_once_and_cached():
    c = _FakeClient(datetime(2026, 6, 1))
    assert sweep.data_floor(c) == datetime(2026, 6, 1)
    assert sweep.data_floor(c) == datetime(2026, 6, 1)
    assert c.queries == 1, "the data floor is a property of the dataset, not of a sweep"


def test_a_failed_floor_lookup_does_not_block_monitoring():
    """Returning None must mean 'no guard', never 'skip everything'.

    Silently stopping detection because a metadata query failed is worse than the artefact
    the guard exists to prevent.
    """

    class _Broken:
        def query(self, *a, **k):
            raise RuntimeError("clickhouse down")

    assert sweep.data_floor(_Broken()) is None


def test_coarse_windows_reaching_before_the_data_are_out_of_range():
    """The arithmetic that caused the explosion, stated directly.

    as_of Jun 2 with data from Jun 1: everything 5d and coarser starts before the floor,
    while 1d and finer sit inside it. That split is exactly the 67,159-vs-201 split observed.
    """
    floor = datetime(2026, 6, 1)
    as_of = datetime(2026, 6, 2)

    before, inside = [], []
    for name, g in GRAIN_REGISTRY.items():
        ws, _ = g.window_for(as_of)
        (before if ws < floor else inside).append(name)

    # Every multi-day grain must be recognised as reaching outside the data.
    for name in ("5d", "10d", "15d", "1w", "2w", "3w"):
        assert name in before, f"{name} window starts before the data floor and must be skipped"
    # ...and the fine grains must NOT be, or the guard would suppress real detection.
    for name in ("1d", "1h", "15m", "5m"):
        assert name in inside, f"{name} is fully inside the data and must still be evaluated"


def test_a_window_fully_inside_the_data_is_never_skipped():
    """The normal case: a sweep late in the dataset keeps every daily-and-finer grain."""
    floor = datetime(2026, 6, 1)
    as_of = datetime(2026, 6, 26)

    for name in ("5m", "15m", "1h", "5h", "10h", "15h", "1d", "5d", "10d", "15d", "1w", "2w", "3w"):
        ws, _ = GRAIN_REGISTRY[name].window_for(as_of)
        assert ws >= floor, f"{name} should be inside the data 25 days in, got {ws}"


def test_the_guard_is_a_start_boundary_not_a_duration_rule():
    """A 3w window is fine once enough history exists -- the test is position, not length.

    Guarding on grain length instead would permanently disable coarse grains, which is the
    obvious wrong fix: three-week erosion is precisely what the coarse grains are for.
    """
    floor = datetime(2026, 6, 1)
    ws_early, _ = GRAIN_REGISTRY["3w"].window_for(datetime(2026, 6, 10))
    ws_later, _ = GRAIN_REGISTRY["3w"].window_for(datetime(2026, 7, 5))

    assert ws_early < floor, "3w is not yet measurable 9 days in"
    assert ws_later >= floor, "the same 3w grain becomes measurable once history exists"


def test_coverage_cell_accounts_the_skip():
    """A skip must be counted and explained, never dropped -- 'no silent sixth option'."""
    cell = sweep.CoverageCell(
        scope_type="global", metric="*", grain="3w",
        window_start=datetime(2026, 5, 12), window_end=datetime(2026, 6, 2),
        skipped_incomplete_window=10,
        skip_reason="window starts before the first event in ad_events",
    )
    assert cell.skipped_incomplete_window == 10
    assert cell.skip_reason
    # cells_total must include these, or coverage would silently stop adding up.
    res = sweep.SweepResult(run_id="r", as_of=datetime(2026, 6, 2), started_at=datetime(2026, 6, 2))
    res.coverage.append(cell)
    assert res.cells_total == 10
