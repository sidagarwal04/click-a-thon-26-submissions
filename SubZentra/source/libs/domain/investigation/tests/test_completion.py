"""What separates a finished Investigation from one that merely stopped."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from zentra_domain_investigation import (
    BoardConfidence,
    CompletionBlocker,
    Conflict,
    Fact,
    GapPriority,
    InvestigationBoard,
    KnowledgeGap,
    assess_completion,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
BOARD_ID = UUID("70000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("30000000-0000-0000-0000-000000000003")


def finished_board() -> InvestigationBoard:
    """A Board with every criterion satisfied, for tests to break one at a time."""
    board = InvestigationBoard.create(
        board_id=BOARD_ID,
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        now=NOW,
    )
    gap = KnowledgeGap(
        gap_id=uuid4(), description="Why did refunds rise?", priority=GapPriority.HIGH
    )
    board.open_gap(gap, now=NOW)
    board.resolve_gap(gap.gap_id, now=NOW)
    board.record_fact(
        Fact(
            fact_id=uuid4(),
            metric="refund_amount",
            value="260.00",
            period="2026-07",
            producing_work_item_id=uuid4(),
        ),
        now=NOW,
    )
    board.set_confidence(BoardConfidence(score=0.86, threshold=0.7), now=NOW)
    return board


def test_a_board_meeting_every_criterion_is_complete() -> None:
    assessment = assess_completion(
        finished_board(), evidence_validated=True, budget_exhausted=False
    )

    assert assessment.complete is True
    assert assessment.blockers == ()
    assert assessment.should_stop is True


def test_an_unresolved_high_priority_gap_blocks_completion() -> None:
    """The question the user asked is itself a HIGH-priority gap, so this is
    also how an unanswered question reports."""
    board = finished_board()
    board.open_gap(
        KnowledgeGap(
            gap_id=uuid4(), description="Which region?", priority=GapPriority.HIGH
        ),
        now=NOW,
    )

    assessment = assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    )

    assert assessment.blockers == (CompletionBlocker.HIGH_PRIORITY_GAP_OPEN,)
    assert assessment.complete is False


def test_a_lower_priority_gap_does_not_block_completion() -> None:
    """A follow-up worth asking is not a reason to call the question
    unanswered. Only the priority that matters blocks."""
    board = finished_board()
    board.open_gap(
        KnowledgeGap(
            gap_id=uuid4(), description="Which channel?", priority=GapPriority.MEDIUM
        ),
        now=NOW,
    )

    assert assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    ).complete


def test_an_unvalidated_recheck_blocks_completion() -> None:
    assessment = assess_completion(
        finished_board(), evidence_validated=False, budget_exhausted=False
    )

    assert assessment.blockers == (CompletionBlocker.EVIDENCE_UNVALIDATED,)


def test_an_open_conflict_blocks_completion() -> None:
    board = finished_board()
    board.open_conflict(
        Conflict(conflict_id=uuid4(), description="two values"), now=NOW
    )

    assessment = assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    )

    assert assessment.blockers == (CompletionBlocker.CONFLICT_UNSETTLED,)


def test_a_documented_conflict_does_not_block_completion() -> None:
    """Documented is a settled outcome. The disagreement reaches the reader,
    which is what the criterion is protecting."""
    board = finished_board()
    conflict = Conflict(conflict_id=uuid4(), description="two values")
    board.open_conflict(conflict, now=NOW)
    board.resolve_conflict(
        conflict.conflict_id,
        resolution="Neither measurement was discarded.",
        now=NOW,
        documented_only=True,
    )

    assert assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    ).complete


def test_confidence_below_the_tenant_threshold_blocks_completion() -> None:
    board = finished_board()
    board.set_confidence(BoardConfidence(score=0.42, threshold=0.7), now=NOW)

    assessment = assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    )

    assert assessment.blockers == (CompletionBlocker.CONFIDENCE_BELOW_THRESHOLD,)


def test_a_board_with_no_confidence_recorded_is_not_complete() -> None:
    """Absent is not the same as adequate. A Board nobody scored has not
    demonstrated anything about its own reliability."""
    board = InvestigationBoard.create(
        board_id=BOARD_ID,
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        now=NOW,
    )

    assessment = assess_completion(
        board, evidence_validated=True, budget_exhausted=False
    )

    assert CompletionBlocker.CONFIDENCE_BELOW_THRESHOLD in assessment.blockers


def test_every_unmet_criterion_is_reported_not_only_the_first() -> None:
    """A run blocked on three things that reports one gets fixed three times."""
    board = InvestigationBoard.create(
        board_id=BOARD_ID,
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        now=NOW,
    )
    board.open_gap(
        KnowledgeGap(gap_id=uuid4(), description="Why?", priority=GapPriority.HIGH),
        now=NOW,
    )
    board.open_conflict(
        Conflict(conflict_id=uuid4(), description="two values"), now=NOW
    )

    assessment = assess_completion(
        board, evidence_validated=False, budget_exhausted=False
    )

    assert set(assessment.blockers) == {
        CompletionBlocker.HIGH_PRIORITY_GAP_OPEN,
        CompletionBlocker.EVIDENCE_UNVALIDATED,
        CompletionBlocker.CONFLICT_UNSETTLED,
        CompletionBlocker.CONFIDENCE_BELOW_THRESHOLD,
    }


def test_an_incomplete_run_stops_anyway_once_the_budget_is_gone() -> None:
    """Stopping is not the same as finishing, and the assessment says which."""
    assessment = assess_completion(
        finished_board(), evidence_validated=False, budget_exhausted=True
    )

    assert assessment.should_stop is True
    assert assessment.complete is False


def test_an_incomplete_run_with_budget_left_does_not_stop() -> None:
    """The whole point: never stop on "the queue emptied" alone."""
    assessment = assess_completion(
        finished_board(), evidence_validated=False, budget_exhausted=False
    )

    assert assessment.should_stop is False


def test_the_narrative_names_what_is_missing_and_carries_no_evidence() -> None:
    """It is persisted to the Board and shown to operators, so it may name
    blockers and nothing else — no metric, no value, no model prose."""
    board = finished_board()
    board.set_confidence(BoardConfidence(score=0.42, threshold=0.7), now=NOW)

    described = assess_completion(
        board, evidence_validated=False, budget_exhausted=True
    ).describe()

    assert "evidence_unvalidated" in described
    assert "confidence_below_threshold" in described
    assert "budget exhausted" in described
    assert "260.00" not in described
    assert "refund" not in described


def test_a_complete_assessment_describes_itself_as_complete() -> None:
    described = assess_completion(
        finished_board(), evidence_validated=True, budget_exhausted=False
    ).describe()

    assert described.startswith("Complete")
