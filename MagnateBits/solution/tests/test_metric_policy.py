"""T5b: unqualified conversion rate must be refused while definition_conflict is open."""

from __future__ import annotations

import pytest

import metric_policy
from ch import CH
from contracts import ConfidenceBreakdown, Finding, InsightReport


@pytest.fixture(scope="module")
def live() -> CH:
    return CH()


def test_load_open_conflicts_finds_conversion(live: CH) -> None:
    conflicts = metric_policy.load_open_conflicts(live)
    assert any(c.subject == "conversion" for c in conflicts)
    conv = next(c for c in conflicts if c.subject == "conversion")
    assert "conversion" in conv.title.lower() or "population" in conv.title.lower()


def test_refuse_unqualified_conversion_question(live: CH) -> None:
    conflicts = metric_policy.load_open_conflicts(live)
    out = metric_policy.refuse_or_qualify_answer(
        "What is our conversion rate?",
        "Conversion rate is 4.5%. Looking good.",
        conflicts,
    )
    assert out is not None
    assert "Refused" in out or "DISPUTED" in out or "definition_conflict" in out
    assert "application_started" in out.lower() or "sessions" in out.lower() or "metric.conversion" in out


def test_qualified_dual_answer_passes(live: CH) -> None:
    conflicts = metric_policy.load_open_conflicts(live)
    text = (
        "Cannot give one number. Under metric.conversion@v1 (application_started denominator) "
        "it is 4.55%; under metric.conversion_rate@v2 (sessions) it is 0.71%. "
        "Definition conflict is open."
    )
    assert metric_policy.refuse_or_qualify_answer("conversion rate?", text, conflicts) is None


def test_enforce_report_replaces_unqualified_finding(live: CH) -> None:
    conflicts = metric_policy.load_open_conflicts(live)
    conf = ConfidenceBreakdown(
        sample_adequacy=0.5,
        statistical_strength=0.5,
        context_support=0.5,
        data_quality=0.5,
        score=0.7,
        method="descriptive",
        n=100,
    )
    report = InsightReport(
        feature_slug="instant_forex",
        run_id="test",
        context_version=1,
        summary="Conversion rate is 12% this week.",
        findings=[
            Finding(
                headline="Conversion rate hit 12%",
                what="conversion rate is 12%",
                why="users bought more",
                so_what="celebrate",
                recommended_action="ship it",
                metric="conversion_rate",
                metric_definition_used="",
                value=0.12,
                confidence=conf,
            )
        ],
    )
    out = metric_policy.enforce_report(report, conflicts)
    assert "DISPUTED" in out.summary or "disputed" in out.summary.lower()
    assert any("disputed" in f.headline.lower() for f in out.findings)
    assert any("metric_policy" in c for c in out.caveats)


def test_explain_metric_marks_disputed(live: CH) -> None:
    info = metric_policy.explain_metric(live, "conversion rate")
    assert info["status"] == "DISPUTED"
