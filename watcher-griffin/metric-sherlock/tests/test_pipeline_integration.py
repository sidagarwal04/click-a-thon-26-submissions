"""Integration test: runs the full pipeline against the live ClickHouse
instance for one known window and asserts on exact numbers (hand-verified
against a direct ClickHouse query in the same session that built this test).
This is what would catch a regression in the contribution/decomposition math
silently breaking trustworthiness before the unseen-incident window --
per CLAUDE.md's "tested, not just demoed" principle.

Requires utils/.env with live ClickHouse Cloud credentials; skipped otherwise.
"""

from datetime import datetime

import pytest

from engine.pipeline import run_investigation


@pytest.mark.integration
def test_known_window_matches_hand_verified_numbers():
    result = run_investigation("revenue", datetime(2026, 6, 29), datetime(2026, 6, 30))
    ev = result.evidence

    assert ev.current_value == pytest.approx(542.98115, rel=1e-6)
    assert ev.baseline_mean == pytest.approx(515.9073945, rel=1e-6)
    assert ev.primary_factor == "requests"
    assert ev.is_anomalous is False  # z ~= 2.39, below the 2.5 threshold -- confirmed not to cry wolf

    # every query that ran is captured verbatim, and none of them errored
    assert len(ev.queries) > 0
    assert all(q.error is None for q in ev.queries)

    # the '' (no-advertiser) bucket must never surface as an attributable segment,
    # at any recursion depth
    assert len(ev.drilldown_levels) >= 1
    for level in ev.drilldown_levels:
        assert all(seg.value != "" for seg in level)
        assert all(seg.source_step for seg in level)  # every segment cites the real query it came from

    # seasonality is always checked, unconditionally
    assert any(r.check == "seasonality" for r in ev.ruled_out)

    # narrator degrades cleanly to the stub provider rather than erroring
    assert result.narration.available is True
    assert result.narration.provider == "stub"
