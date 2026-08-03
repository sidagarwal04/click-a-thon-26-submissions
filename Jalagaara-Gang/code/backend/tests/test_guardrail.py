"""JAL-88: the guardrail must catch fabricated MAGNITUDE, not just fabricated digits.

Regression source: a live run produced a bundle holding `observed: 18.33` - correct, since
the dataset totals 17,020.36 revenue across 840 hours - and the narrator wrote "$18.33M".
Every digit was genuine, so the old digit-only check returned passed=True while the prose
overstated revenue a millionfold. That is exactly the failure mode the trustworthiness
criterion penalises, and reporting it as verified made it worse.
"""
from pathlib import Path

import pytest

from models import EvidenceBundle
from narrator.guardrail import verify

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_bundle.json"


@pytest.fixture
def bundle() -> EvidenceBundle:
    """A bundle whose anomaly numbers are bare floats, as the pipeline produces."""
    b = EvidenceBundle.model_validate_json(FIXTURE.read_text())
    b.anomaly.observed = 18.33
    b.anomaly.expected = 18.96
    b.anomaly.abs_delta = -0.63
    b.anomaly.pct_delta = -0.0332
    return b


# ---- digits (existing behaviour must not regress) ---------------------------

def test_bare_numbers_from_the_bundle_pass(bundle):
    v = verify(bundle, "Revenue fell to 18.33 from an expected 18.96.")
    assert v.passed is True
    assert v.unverified_numbers == []


def test_invented_digits_are_caught(bundle):
    v = verify(bundle, "Revenue fell to 12345.")
    assert v.passed is False
    assert "12345" in v.unverified_numbers


def test_percentage_form_of_a_fraction_is_allowed(bundle):
    """pct_delta -0.0332 may legitimately be written as 3.32%."""
    assert verify(bundle, "a 3.32% decrease").passed is True


# ---- magnitude (the actual bug) --------------------------------------------

def test_the_exact_reported_failure_is_now_caught(bundle):
    """Verbatim from the live run that exposed this."""
    prose = ("A significant revenue drop was detected with an anomaly score of -22.0, showing "
             "revenue falling to $18.33M against an expected $18.96M. The absolute decline was "
             "$0.63M, representing a -3.32% decrease from expectations.")

    v = verify(bundle, prose)

    assert v.passed is False, "the millionfold overstatement must not pass"
    assert any("18.33" in u for u in v.unverified_numbers)


@pytest.mark.parametrize("prose", [
    "revenue fell to $18.33M",
    "revenue fell to 18.33 million",
    "revenue fell to $18.33 billion",
    "revenue fell to 18.33 trillion",
    "revenue fell to 18.33K",
])
def test_scale_suffixes_and_currency_are_rejected(bundle, prose):
    assert verify(bundle, prose).passed is False


def test_currency_symbol_alone_is_rejected(bundle):
    """The digits are real; the dollar sign is invented."""
    v = verify(bundle, "revenue fell to $18.33")
    assert v.passed is False
    assert any("$" in u for u in v.unverified_numbers)


def test_a_word_starting_with_a_suffix_letter_is_not_a_false_positive(bundle):
    """'18.33 metrics' must not trip the 'm' suffix rule."""
    assert verify(bundle, "we examined 18.33 metrics").passed is True


def test_failure_lists_the_offending_token(bundle):
    v = verify(bundle, "revenue fell to $18.33M")
    assert v.unverified_numbers, "the offender must be named, not just flagged"


def test_clean_prose_still_passes_end_to_end(bundle):
    prose = ("Revenue fell to 18.33 against an expected 18.96, a 3.32% decrease. "
             "Localization did not complete for this investigation.")
    assert verify(bundle, prose).passed is True
