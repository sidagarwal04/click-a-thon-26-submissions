"""The Draft Finding: what Insight proposes, before policy or a human decides.

A Phase 1 Finding was narrative — headline, summary, and a bag of opaque
`artifact://` strings. Everything a reviewer needed to separate measurement from
interpretation, or to see that a contradiction was still open, was buried in
prose. These tests pin the parts that have to be *data* for Replay to be able to
show them at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import ConfidenceOutcome

from zentra_domain_investigation import (
    Claim,
    ClaimKind,
    Contradiction,
    DraftFinding,
    DraftFindingError,
    RootCauseState,
)

NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
TENANT_ID = UUID("aa000000-0000-0000-0000-000000000001")
INVESTIGATION_ID = UUID("bb000000-0000-0000-0000-000000000001")
CITATION_ID = UUID("cc000000-0000-0000-0000-000000000001")


def claim(position: int, kind: ClaimKind = ClaimKind.OBSERVED, **overrides) -> Claim:
    measured = kind is ClaimKind.OBSERVED
    defaults = {
        "claim_id": uuid4(),
        "kind": kind,
        "text": f"Claim {position}",
        "position": position,
        "metric": "refund_amount" if measured else None,
        "value": "260.00" if measured else None,
        "period": "July 2026" if measured else None,
        "citation_ids": (CITATION_ID,) if measured else (),
    }
    return Claim(**(defaults | overrides))


def draft(**overrides) -> DraftFinding:
    defaults = {
        "draft_finding_id": uuid4(),
        "tenant_id": TENANT_ID,
        "investigation_id": INVESTIGATION_ID,
        "version": 1,
        "created_at": NOW,
        "produced_by_execution_id": None,
        "headline": "EU refunds rose $240 in July.",
        "summary": "Governed EU refund amount rose from $20 to $260.",
        "claims": (claim(0), claim(1, ClaimKind.INTERPRETATION)),
        "contradictions": (),
        "root_cause": RootCauseState.UNRESOLVED,
        "confidence": ConfidenceOutcome(
            score=0.72, calibration_method="capped_sample_size"
        ),
    }
    return DraftFinding(**(defaults | overrides))


def test_a_claim_states_whether_it_is_measured_or_interpreted() -> None:
    """The single most important thing a reviewer has to be able to tell apart,
    and prose cannot be relied on to carry it."""
    observed, interpretation = draft().claims

    assert observed.kind is ClaimKind.OBSERVED
    assert interpretation.kind is ClaimKind.INTERPRETATION


def test_claim_order_is_explicit_rather_than_incidental() -> None:
    """Persistence and API round trips reorder tuples freely. Position is what
    survives them; relying on insertion order would not."""
    assert [c.position for c in draft().claims] == [0, 1]


def test_claim_positions_must_be_contiguous_from_zero() -> None:
    """A gap means a claim was dropped somewhere between Insight and the
    reader. Failing here is how that gets noticed."""
    with pytest.raises(DraftFindingError, match="contiguous"):
        draft(claims=(claim(0), claim(2)))

    with pytest.raises(DraftFindingError, match="contiguous"):
        draft(claims=(claim(1), claim(2)))


def test_duplicate_claim_positions_are_refused() -> None:
    with pytest.raises(DraftFindingError, match="contiguous"):
        draft(claims=(claim(0), claim(0)))


def test_a_draft_with_no_claims_is_allowed_but_ordered_trivially() -> None:
    """Whether an empty draft may publish is the publication policy's call,
    not this type's."""
    assert draft(claims=()).claims == ()


def test_a_contradiction_is_typed_data_not_a_sentence_in_the_summary() -> None:
    """`Finding.summary` carried these as prose, which meant nothing could
    render 'unresolved contradiction' as a state."""
    unresolved = Contradiction(detail="Recheck disagreed on sample size.")

    assert unresolved.resolved is False
    assert draft(contradictions=(unresolved,)).contradictions == (unresolved,)


def test_root_cause_is_a_state_rather_than_an_absence() -> None:
    """ADR 0011 requires the product to *say* 'root cause unresolved'. A
    missing field says nothing; a typed state can be rendered."""
    assert draft().root_cause is RootCauseState.UNRESOLVED
    assert [state.value for state in RootCauseState] == ["unresolved"]


def test_a_claim_can_carry_several_citations_in_order() -> None:
    """Citations arrive in a later slice; the shape that will hold them has to
    exist now or that slice becomes a schema migration."""
    first, second = uuid4(), uuid4()

    carried = draft(claims=(claim(0, citation_ids=(first, second)),))

    assert carried.claims[0].citation_ids == (first, second)


def test_confidence_is_the_bounded_outcome_not_a_fresh_number() -> None:
    """Insight does not get to score itself past what the evidence allows, so
    the draft carries the already-bounded outcome and the reason for it."""
    bounded = draft().confidence

    assert bounded is not None
    assert bounded.score == 0.72
    assert bounded.calibration_method == "capped_sample_size"


def test_a_draft_is_owned_by_exactly_one_tenant_and_investigation() -> None:
    subject = draft()

    assert subject.tenant_id == TENANT_ID
    assert subject.investigation_id == INVESTIGATION_ID


def test_an_observed_claim_must_carry_its_measurement() -> None:
    """Otherwise `observed` is a formatting choice rather than a statement
    about evidence, and a reader is asked to take the label on trust."""
    with pytest.raises(DraftFindingError, match="no measurement"):
        draft(claims=(claim(0, metric=None),))

    with pytest.raises(DraftFindingError, match="no measurement"):
        draft(claims=(claim(0, value=None),))


def test_an_interpretation_needs_no_measurement_of_its_own() -> None:
    """It is a reading of someone else's."""
    reading = claim(0, ClaimKind.INTERPRETATION)

    assert draft(claims=(reading,)).claims[0].metric is None


def test_an_observed_claim_carries_the_period_its_value_covers() -> None:
    """"Refunds were $260" is not a fact until it says when."""
    measured = draft().claims[0]

    assert measured.metric == "refund_amount"
    assert measured.value == "260.00"
    assert measured.period == "July 2026"


def test_an_observed_claim_must_cite_its_evidence() -> None:
    """A substantive claim a reader cannot follow is the thing Phase 2 exists
    to stop shipping."""
    with pytest.raises(DraftFindingError, match="cites no evidence"):
        draft(claims=(claim(0, citation_ids=()),))


def test_an_interpretation_needs_no_citation_of_its_own() -> None:
    reading = draft(claims=(claim(0, ClaimKind.INTERPRETATION),))

    assert reading.claims[0].citation_ids == ()


def test_two_claims_can_rest_on_the_same_evidence() -> None:
    """Sharing is the point. Two claims about July's refunds rest on one
    measurement, and duplicating it would let the two drift."""
    shared = draft(
        claims=(
            claim(0, citation_ids=(CITATION_ID,)),
            claim(1, citation_ids=(CITATION_ID,)),
        )
    )

    assert shared.claims[0].citation_ids == shared.claims[1].citation_ids


def test_one_claim_can_cite_several_records_in_order() -> None:
    """A claim comparing two periods rests on two measurements, and which came
    first is part of what it says."""
    second = UUID("cc000000-0000-0000-0000-000000000002")

    cited = draft(claims=(claim(0, citation_ids=(CITATION_ID, second)),))

    assert cited.claims[0].citation_ids == (CITATION_ID, second)


def test_a_draft_whose_evidence_was_erased_still_loads() -> None:
    """The failure this invariant nearly caused.

    Erasure empties a claim's value while leaving the field. Rejecting an
    empty string would raise on every load of an Investigation whose evidence
    a Tenant deleted — so the deletion would destroy the process record it
    exists to preserve.
    """
    erased = draft(claims=(claim(0, value="", period=None),))

    assert erased.claims[0].value == ""
    assert erased.claims[0].metric == "refund_amount"


def test_an_observed_claim_still_needs_a_metric_and_a_value_field() -> None:
    """Relaxing to `is None` must not relax it to nothing."""
    with pytest.raises(DraftFindingError, match="no measurement"):
        draft(claims=(claim(0, value=None),))
    with pytest.raises(DraftFindingError, match="no measurement"):
        draft(claims=(claim(0, metric=None),))
