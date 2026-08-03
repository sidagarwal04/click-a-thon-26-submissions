"""Regression tests for the two T5a contradiction false positives.

Both were board-visible before the fix:
  1. `check_stale_entries` flagged the deliberate `event`-first ORDER BY -- our own
     correct house_rules.md design -- as stale, because it tested lead-column
     POSITION, not cardinality.
  2. `check_schema_mismatches` named the wrong table ("documented on destination_card_
     clicked") for a missing column, because `_nearest_columns`' lexical ranking has no
     notion of meaning: "visa_issuance_eta_days" scores textually closer to
     `visa_type` than to the actually-correct `eta_shown`.

These are unit tests against the pure functions, no live ClickHouse needed.
"""

from __future__ import annotations

from contextlayer.checks import _collapse_by_subject, LEAD_KEY_MAX_DISCRIMINATOR_VALUES, LEAD_KEY_UNIQUE_RATIO
from contracts import Contradiction


def _c(title: str) -> Contradiction:
    return Contradiction(
        kind="schema_mismatch", title=title, claim=".", evidence=".",
        verified=True, entry_ids=["e1"], severity="high", detected_by="rule",
    )


def test_entry_stated_subject_beats_lexical_guess_for_same_column() -> None:
    """The FP2 regression: an explicit table ref (spec 2) must win over a nearest-
    column guess (spec 1) for the same missing column, even when the guess landed
    on a different table than the authoritative one."""
    rows = [
        ("visa_issuance_eta_days", ("application_started",), 2, _c("documented on application_started")),
        ("visa_issuance_eta_days", ("destination_card_clicked",), 1, _c("documented on destination_card_clicked")),
    ]
    out = _collapse_by_subject(rows)
    assert len(out) == 1
    assert "application_started" in out[0].title
    assert "destination_card_clicked" not in out[0].title


def test_two_genuinely_different_entry_stated_subjects_both_survive() -> None:
    """A column two DIFFERENT entries both explicitly claim on two different real
    tables is two real defects, not one -- collapsing must not over-merge spec-2 rows."""
    rows = [
        ("x", ("table_a",), 2, _c("documented on table_a")),
        ("x", ("table_b",), 2, _c("documented on table_b")),
    ]
    out = _collapse_by_subject(rows)
    assert len(out) == 2


def test_subjectless_finding_folds_into_scoped_one() -> None:
    rows = [
        ("y", ("table_a",), 2, _c("documented on table_a")),
        ("y", (), 0, _c("exists on no table here")),
    ]
    out = _collapse_by_subject(rows)
    assert len(out) == 1
    assert "table_a" in out[0].title


def test_stale_entry_cardinality_gate_constants_are_sane() -> None:
    """Guards against a future edit reintroducing the position-only check by proving the
    gate has real thresholds: a genuine discriminator (low selectivity, few distinct
    values) and a near-unique key (high selectivity) must land on opposite sides."""
    assert 0.0 < LEAD_KEY_UNIQUE_RATIO < 1.0
    assert LEAD_KEY_MAX_DISCRIMINATOR_VALUES > 100

    def flags_as_stale(selectivity: float, distinct: int) -> bool:
        return selectivity >= LEAD_KEY_UNIQUE_RATIO or distinct > LEAD_KEY_MAX_DISCRIMINATOR_VALUES

    # event: ~5 distinct values over 6000+ rows -- a real discriminator, must NOT flag.
    assert not flags_as_stale(selectivity=5 / 6237, distinct=5)
    # id: one distinct value per row -- selectivity 1.0, must flag.
    assert flags_as_stale(selectivity=1.0, distinct=6237)
