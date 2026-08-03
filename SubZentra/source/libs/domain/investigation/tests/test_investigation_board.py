from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from zentra_domain_investigation import (
    BoardConfidence,
    BoardTransitionError,
    Conflict,
    ConflictStatus,
    Fact,
    GapPriority,
    Hypothesis,
    HypothesisStatus,
    InvestigationBoard,
    KnowledgeGap,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
BOARD_ID = UUID("70000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("30000000-0000-0000-0000-000000000003")


def new_board() -> InvestigationBoard:
    return InvestigationBoard.create(
        board_id=BOARD_ID,
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        now=NOW,
    )


def test_open_gaps_excludes_resolved_ones() -> None:
    board = new_board()
    low = KnowledgeGap(gap_id=uuid4(), description="minor", priority=GapPriority.LOW)
    high = KnowledgeGap(
        gap_id=uuid4(), description="what drove it", priority=GapPriority.HIGH
    )
    board.open_gap(low, now=NOW)
    board.open_gap(high, now=NOW)

    board.resolve_gap(low.gap_id, now=NOW + timedelta(seconds=1))

    assert board.open_gaps == (high,)
    assert board.high_priority_open_gaps == (high,)
    assert board.updated_at == NOW + timedelta(seconds=1)


def test_resolve_gap_requires_a_gap_on_this_board() -> None:
    board = new_board()

    with pytest.raises(BoardTransitionError, match="not on this Board"):
        board.resolve_gap(uuid4(), now=NOW)


def test_hypothesis_cannot_be_settled_back_to_open() -> None:
    board = new_board()
    hypothesis = Hypothesis(hypothesis_id=uuid4(), statement="Refunds rose in EU")
    board.open_hypothesis(hypothesis, now=NOW)

    with pytest.raises(BoardTransitionError, match="cannot be settled"):
        board.settle_hypothesis(
            hypothesis.hypothesis_id, status=HypothesisStatus.OPEN, now=NOW
        )

    board.settle_hypothesis(
        hypothesis.hypothesis_id, status=HypothesisStatus.SUPPORTED, now=NOW
    )
    assert hypothesis.status is HypothesisStatus.SUPPORTED


def test_conflict_resolution_can_be_documented_without_being_resolved() -> None:
    board = new_board()
    conflict = Conflict(conflict_id=uuid4(), description="Two counts disagree")
    board.open_conflict(conflict, now=NOW)
    assert board.unresolved_conflicts == (conflict,)

    board.resolve_conflict(
        conflict.conflict_id,
        resolution="Escalated to Human Approval",
        now=NOW,
        documented_only=True,
    )

    assert conflict.status is ConflictStatus.DOCUMENTED
    assert board.unresolved_conflicts == ()


def test_resolve_conflict_requires_an_explanation() -> None:
    board = new_board()
    conflict = Conflict(conflict_id=uuid4(), description="disagreement")
    board.open_conflict(conflict, now=NOW)

    with pytest.raises(ValueError, match="explanation"):
        board.resolve_conflict(conflict.conflict_id, resolution="  ", now=NOW)


def test_confidence_meets_threshold_only_when_scored_and_above() -> None:
    unscored = BoardConfidence(score=None, threshold=0.7)
    below = BoardConfidence(score=0.5, threshold=0.7)
    above = BoardConfidence(score=0.8, threshold=0.7)

    assert unscored.meets_threshold is False
    assert below.meets_threshold is False
    assert above.meets_threshold is True


def test_record_fact_appends_and_bumps_updated_at() -> None:
    board = new_board()
    fact = Fact(
        fact_id=uuid4(),
        metric="Commerce.refundAmount",
        value="120000",
        period="2026-07",
        producing_work_item_id=uuid4(),
    )

    board.record_fact(fact, now=NOW + timedelta(seconds=5))

    assert board.facts == [fact]
    assert board.updated_at == NOW + timedelta(seconds=5)


def fact(
    *, value: str, period: str | None = "2026-07", metric: str = "refund_amount"
) -> Fact:
    return Fact(
        fact_id=uuid4(),
        metric=metric,
        value=value,
        period=period,
        producing_work_item_id=uuid4(),
    )


def test_a_second_measurement_disagreeing_is_a_contradiction() -> None:
    """Two Work Items measuring the same thing must agree. When they do not,
    one of them is wrong and the Board may not silently keep both."""
    board = new_board()
    incumbent = fact(value="120000")
    board.record_fact(incumbent, now=NOW)

    assert board.contradicted_by(fact(value="98000")) is incumbent


def test_a_second_measurement_agreeing_is_corroboration_not_a_conflict() -> None:
    """A fan-out that re-measures what the primary Analyst already measured is
    the cheapest confirmation available; reading it as a conflict would punish
    the investigation for checking itself."""
    board = new_board()
    board.record_fact(fact(value="120000"), now=NOW)

    assert board.contradicted_by(fact(value="120000")) is None


def test_the_same_metric_over_a_different_period_does_not_contradict() -> None:
    board = new_board()
    board.record_fact(fact(value="120000", period="2026-06"), now=NOW)

    assert board.contradicted_by(fact(value="98000", period="2026-07")) is None


def test_a_different_metric_over_the_same_period_does_not_contradict() -> None:
    board = new_board()
    board.record_fact(fact(value="120000", metric="refund_amount"), now=NOW)

    assert board.contradicted_by(fact(value="98000", metric="order_count")) is None


def test_an_empty_board_contradicts_nothing() -> None:
    assert new_board().contradicted_by(fact(value="120000")) is None


def test_a_periodless_fact_contradicts_only_another_periodless_one() -> None:
    """`None` is a period like any other here: a lifetime total and a July
    total are different measurements, not disagreeing ones."""
    board = new_board()
    lifetime = fact(value="120000", period=None)
    board.record_fact(lifetime, now=NOW)

    assert board.contradicted_by(fact(value="98000", period="2026-07")) is None
    assert board.contradicted_by(fact(value="98000", period=None)) is lifetime
