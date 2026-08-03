"""Regression test for the numeric grounding check.

Locks in the real defect from the first end-to-end run: the Analytics Agent asserted
a median of 0 while the queries it cited returned 37,536 / 29,926 / 26,127. The guard
must demote that finding and leave a true claim from the same queries alone.
"""

from __future__ import annotations

import pytest

import grounding
from contracts import ConfidenceBreakdown, Finding, InsightReport, QueryRun


def _run(name: str, rows: list[dict]) -> QueryRun:
    return QueryRun(name=name, sql="SELECT 1", rows=len(rows), duration_ms=1, result=rows)


def _finding(headline: str, value: float, cites: list[str]) -> Finding:
    return Finding(
        headline=headline, what=".", why=".", so_what=".", recommended_action=".",
        metric="m", value=value, supporting_queries=cites, severity="watch",
        confidence=ConfidenceBreakdown(
            sample_adequacy=0.9, statistical_strength=0.8, context_support=0.6,
            data_quality=0.9, score=0.77, method="descriptive", n=1271,
        ),
    )


DIST = _run("t05_dist", [
    {"segment": "US", "n": 134, "p50": 37536.0},
    {"segment": "TH", "n": 112, "p50": 29926.0},
    {"segment": "SG", "n": 101, "p50": 26127.0},
])


def _verify(f: Finding) -> Finding:
    rep = InsightReport(feature_slug="x", run_id="x", context_version=1, summary="", findings=[f])
    return grounding.verify(rep, [DIST])[0].findings[0]


def test_demotes_number_absent_from_cited_queries() -> None:
    out = _verify(_finding("Median is 0 in every segment", 0.0, ["t05_dist"]))
    assert out.severity == "info"
    assert out.confidence.score <= 0.25
    assert out.caveats and out.caveats[0].startswith("UNVERIFIED")


def test_keeps_number_present_in_cited_queries() -> None:
    out = _verify(_finding("US median is 37,536", 37536.0, ["t05_dist"]))
    assert out.severity == "watch"
    assert out.confidence.score == pytest.approx(0.77)
    assert not out.caveats


def test_percentage_restatement_is_grounded() -> None:
    """A frame value of 0.1079 may legitimately be stated as 10.79%."""
    run = _run("t03", [{"segment": "GB", "rate": 0.1079}])
    rep = InsightReport(feature_slug="x", run_id="x", context_version=1, summary="",
                        findings=[_finding("GB attaches at 10.79%", 10.79, ["t03"])])
    assert grounding.verify(rep, [run])[0].findings[0].severity == "watch"


def test_finding_citing_nothing_is_demoted() -> None:
    out = _verify(_finding("Vibes are down", 42.0, []))
    assert out.severity == "info"
    assert "cites no query" in out.caveats[0]
