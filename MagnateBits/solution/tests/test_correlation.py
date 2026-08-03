"""Correlation analysis: T11/T12 query templates, Fisher-z significance, confidence wiring.

Fills the one gap identified against the problem statement's Analytics Agent bullet
("trends, anomalies, segment comparisons, and correlations") -- everything else already
had a template; correlation did not.

Design constraints these tests lock in:
  - No raw rows leave ClickHouse: the templates return (n, r), never per-row data.
  - A measure captured only AT OR AFTER the funnel outcome step cannot be correlated
    with reaching it (circular by construction) -- refused, not silently NaN.
  - Two measures that never co-occur on the same event cannot be correlated either.
  - The Fisher z-transform significance test feeds the SAME confidence pipeline as
    every other method (no special-cased scoring path).
"""

from __future__ import annotations

import math

import pytest

import confidence as conf
import queries.stats as stats
import queries.templates as T
from contracts import FeatureSemantics, MeasureSpec


def _sem(**overrides) -> FeatureSemantics:
    base = dict(
        feature_slug="corr_test",
        table_fqn="atlys.f_corr_test_events",
        event_types=["a_opened", "a_confirmed"],
        entity_key="entity_id",
        ordered_steps=["a_opened", "a_confirmed"],
        measures=[
            MeasureSpec(column="retries", kind="count", scoped_to_events=["a_opened"]),
            MeasureSpec(column="amount", kind="money", scoped_to_events=["a_confirmed"]),
            MeasureSpec(column="delay_ms", kind="duration_ms", scoped_to_events=["a_opened"]),
        ],
    )
    base.update(overrides)
    return FeatureSemantics(**base)


# ---------------------------------------------------------------------------
# pearson_significance (queries/stats.py) -- pure arithmetic
# ---------------------------------------------------------------------------


def test_pearson_significance_matches_hand_computed_fisher_z() -> None:
    r, n = 0.42, 200
    z_expected = math.atanh(r) * math.sqrt(n - 3)
    p_expected = math.erfc(abs(z_expected) / math.sqrt(2.0))
    z, p = stats.pearson_significance(r, n)
    assert z == pytest.approx(z_expected, rel=1e-9)
    assert p == pytest.approx(p_expected, rel=1e-9)


def test_pearson_significance_degenerate_n_returns_no_evidence() -> None:
    assert stats.pearson_significance(0.9, 3) == (0.0, 1.0)
    assert stats.pearson_significance(0.9, 0) == (0.0, 1.0)


def test_pearson_significance_clamps_perfect_correlation() -> None:
    # r=1.0 would make atanh diverge; must not raise or return inf/nan.
    z, p = stats.pearson_significance(1.0, 500)
    assert math.isfinite(z)
    assert 0.0 <= p <= 1.0


def test_pearson_significance_zero_r_is_not_significant() -> None:
    z, p = stats.pearson_significance(0.0, 500)
    assert z == pytest.approx(0.0)
    assert p == pytest.approx(1.0)


def test_pearson_significance_stronger_r_is_more_significant() -> None:
    _, p_weak = stats.pearson_significance(0.1, 200)
    _, p_strong = stats.pearson_significance(0.6, 200)
    assert p_strong < p_weak


# ---------------------------------------------------------------------------
# T11 -- measure vs measure
# ---------------------------------------------------------------------------


def test_t11_correlates_measures_sharing_an_event() -> None:
    sem = _sem()
    q = T.t11_measure_correlation(sem, "retries", "delay_ms")
    assert q.kind == "correlation"
    assert "corrStable" in q.sql
    assert "a_opened" in q.sql  # scope clause restricts to the shared event
    assert "limit" in q.sql.lower()


def test_t11_refuses_measures_that_never_co_occur() -> None:
    sem = _sem()
    with pytest.raises(T.TemplateError, match="never co-occur"):
        T.t11_measure_correlation(sem, "retries", "amount")  # opened vs confirmed


def test_t11_refuses_same_column_twice() -> None:
    sem = _sem()
    with pytest.raises(T.TemplateError):
        T.t11_measure_correlation(sem, "retries", "retries")


def test_correlatable_measure_pairs_excludes_non_cooccurring() -> None:
    sem = _sem()
    pairs = T._correlatable_measure_pairs(sem)
    names = {(a.column, b.column) for a, b in pairs}
    assert ("retries", "delay_ms") in names  # both on a_opened
    assert ("retries", "amount") not in names  # different events
    assert ("amount", "delay_ms") not in names


# ---------------------------------------------------------------------------
# T12 -- measure vs funnel completion
# ---------------------------------------------------------------------------


def test_t12_correlates_early_measure_with_completion() -> None:
    sem = _sem()
    q = T.t12_measure_vs_completion(sem, "retries")  # captured on step 1, outcome is step 2
    assert q.kind == "correlation"
    assert "corrStable" in q.sql
    assert "limit" in q.sql.lower()


def test_t12_refuses_measure_captured_only_at_the_outcome_step() -> None:
    """The trap this whole feature exists to catch: `amount` is captured only on
    a_confirmed, which IS the outcome step -- every row with a value already
    succeeded, so correlating it with success is circular, not predictive."""
    sem = _sem()
    with pytest.raises(T.TemplateError, match="circular"):
        T.t12_measure_vs_completion(sem, "amount")


def test_t12_allows_unscoped_measure() -> None:
    sem = _sem(
        measures=[MeasureSpec(column="group_size", kind="count", scoped_to_events=[])]
    )
    q = T.t12_measure_vs_completion(sem, "group_size")
    assert "corrStable" in q.sql


def test_build_all_silently_skips_circular_measures() -> None:
    """The default plan must not crash on a feature whose only measure is
    outcome-scoped -- it should just produce a plan without a T12 for it."""
    sem = _sem(
        measures=[MeasureSpec(column="amount", kind="money", scoped_to_events=["a_confirmed"])]
    )
    plan = T.build_all(sem)
    assert not any("t12" in q.name for q in plan)


# ---------------------------------------------------------------------------
# Catalog wiring
# ---------------------------------------------------------------------------


def test_catalog_lists_both_correlation_templates() -> None:
    sem = _sem()
    ids = {info.id for info in T.catalog(sem)}
    assert "t11_measure_correlation" in ids
    assert "t12_measure_vs_completion" in ids


def test_catalog_marks_t11_unavailable_with_one_measure() -> None:
    sem = _sem(measures=[MeasureSpec(column="retries", kind="count", scoped_to_events=[])])
    info = next(i for i in T.catalog(sem) if i.id == "t11_measure_correlation")
    assert info.available is False


# ---------------------------------------------------------------------------
# Confidence scoring -- same pipeline as every other method, no special casing
# ---------------------------------------------------------------------------


def test_confidence_compute_scores_pearson_correlation() -> None:
    ev = conf.Evidence(method="pearson_correlation", n=200, correlation_r=0.42)
    b = conf.compute(ev, [])
    assert b.method == "pearson_correlation"
    z, p_expected = stats.pearson_significance(0.42, 200)
    assert b.p_value == pytest.approx(p_expected, abs=1e-6)
    assert b.statistical_strength == pytest.approx(1.0 - p_expected, abs=1e-4)


def test_confidence_correlation_weak_r_scores_low_strength() -> None:
    strong = conf.compute(conf.Evidence(method="pearson_correlation", n=500, correlation_r=0.8), [])
    weak = conf.compute(conf.Evidence(method="pearson_correlation", n=500, correlation_r=0.02), [])
    assert strong.statistical_strength > weak.statistical_strength


def test_confidence_correlation_missing_r_defaults_conservatively() -> None:
    ev = conf.Evidence(method="pearson_correlation", n=200, correlation_r=None)
    b = conf.compute(ev, [])
    assert b.statistical_strength == pytest.approx(0.0, abs=1e-6)
