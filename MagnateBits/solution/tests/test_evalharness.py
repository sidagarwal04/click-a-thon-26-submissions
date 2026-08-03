"""Unit tests for `evalharness` (T8) -- the module with the least test coverage of any
non-trivial file in the repo, which is exactly how its verdict-logic bug went unnoticed
(see `_topology_verdict`'s docstring in evalharness.py for what it was and why).

No ClickHouse, no LLM: `_topology_verdict` and `_run_classification` are pure functions
over already-fetched data, deliberately factored out so they're testable without a live
pipeline run.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import evalharness as eh


# --------------------------------------------------------------------------
# _topology_verdict -- Table 2's pass/fail decision
# --------------------------------------------------------------------------


def test_verdict_all_queries_ok_is_pass():
    assert eh._topology_verdict(5, 5) == "PASS"


def test_verdict_zero_queries_generated_is_review_not_pass():
    """The bug this file exists to catch: 0/0 must never read as PASS -- the harness
    cannot tell 'legitimately nothing to query' from 'template-coverage gap' apart."""
    verdict = eh._topology_verdict(0, 0)
    assert verdict != "PASS"
    assert verdict.startswith("REVIEW")


def test_verdict_partial_failure_is_fail_not_pass():
    """The other half of the bug: a partially-failing run must not collapse to PASS
    just because the failures were captured in a flag."""
    verdict = eh._topology_verdict(3, 5)
    assert verdict.startswith("FAIL")
    assert "2/5" in verdict


def test_verdict_total_failure_is_fail():
    verdict = eh._topology_verdict(0, 5)
    assert verdict.startswith("FAIL")
    assert "5/5" in verdict


def test_verdict_one_off_by_one_short_of_full_is_still_fail():
    """Guards against a future '90% is good enough' threshold creeping back in --
    every generated query is expected to run; there is no partial-credit fraction."""
    verdict = eh._topology_verdict(99, 100)
    assert verdict.startswith("FAIL")


# --------------------------------------------------------------------------
# _run_classification / _best_run_id -- Table 1's read-from-history logic
# --------------------------------------------------------------------------


def _row(run_id: str, ts: datetime, stage: str, status: str, detail: str = "") -> dict:
    return {"run_id": run_id, "ts": ts, "stage": stage, "status": status, "detail": detail}


def test_best_run_id_prefers_the_run_that_reached_further():
    t0 = datetime(2026, 1, 1)
    rows = [
        _row("abandoned", t0, "context.load", "ok"),
        _row("abandoned", t0 + timedelta(seconds=1), "instrumentation", "ok"),
        _row("clean", t0 + timedelta(minutes=1), "context.load", "ok"),
        _row("clean", t0 + timedelta(minutes=1, seconds=1), "instrumentation", "ok"),
        _row("clean", t0 + timedelta(minutes=1, seconds=2), "context.reconcile", "ok"),
        _row("clean", t0 + timedelta(minutes=1, seconds=3), "analytics", "ok"),
        _row("clean", t0 + timedelta(minutes=1, seconds=4), "report", "ok"),
    ]
    assert eh._best_run_id(rows) == "clean"


def test_best_run_id_empty_rows_returns_none():
    assert eh._best_run_id([]) is None


def test_run_classification_no_report_stage_is_incomplete():
    t0 = datetime(2026, 1, 1)
    rows = [
        _row("r1", t0, "context.load", "ok"),
        _row("r1", t0 + timedelta(seconds=1), "instrumentation", "ok"),
    ]
    verdict = eh._run_classification(rows, "r1")
    assert verdict.startswith("INCOMPLETE")
    assert "instrumentation" in verdict


def test_run_classification_abandoned_after_reports_the_chronologically_last_stage():
    """'instrumentation' > 'context.reconcile' alphabetically despite running first --
    a run that got past instrumentation must not be reported as abandoned there."""
    t0 = datetime(2026, 1, 1)
    rows = [
        _row("r1", t0, "context.load", "ok"),
        _row("r1", t0 + timedelta(seconds=1), "instrumentation", "ok"),
        _row("r1", t0 + timedelta(seconds=2), "context.reconcile", "ok"),
    ]
    verdict = eh._run_classification(rows, "r1")
    assert "context.reconcile" in verdict
    assert "abandoned after `instrumentation`" not in verdict


def test_run_classification_clean_report_and_analytics_ok_is_clean():
    t0 = datetime(2026, 1, 1)
    rows = [
        _row("r1", t0, "analytics", "ok"),
        _row("r1", t0 + timedelta(seconds=1), "report", "ok"),
    ]
    assert eh._run_classification(rows, "r1") == "CLEAN"


def test_run_classification_analytics_error_is_degraded_with_reason():
    t0 = datetime(2026, 1, 1)
    rows = [
        _row("r1", t0, "analytics", "error", detail="LLM timed out"),
        _row("r1", t0 + timedelta(seconds=1), "report", "warn"),
    ]
    verdict = eh._run_classification(rows, "r1")
    assert verdict.startswith("DEGRADED")
    assert "LLM timed out" in verdict


# --------------------------------------------------------------------------
# discovery -- must not silently see nothing
# --------------------------------------------------------------------------


def test_discover_spec_dirs_finds_the_known_specs():
    dirs = eh.discover_spec_dirs()
    assert len(dirs) >= 5, f"expected the 5 known spec dirs, found {len(dirs)}"


def test_discover_mock_dirs_finds_the_generated_topologies():
    dirs = eh.discover_mock_dirs()
    assert len(dirs) >= 4, f"expected the 4 mock topologies, found {len(dirs)}"
