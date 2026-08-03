"""When an Investigation is finished — and when it has merely stopped.

ADR-0026 Phase 4. An Orchestrator Loop whose queue has emptied has not
established that the question is answered; it has established that it ran out
of things it happened to schedule. Those are different claims, and a product
that reports the second as the first is the confident-wrong-answer failure this
system exists to avoid.

**Not a publication gate.** Whether a Draft Finding may become a Finding is
deterministic Investigation policy (ADR-0011, `evaluate_publication`), and it
answers a different question: *may the reader be shown this?* This module
answers *is there more work worth doing?* The two overlap — both care about the
recheck and the threshold — but they are not the same decision and neither may
be derived from the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .investigation_board import InvestigationBoard


class CompletionBlocker(StrEnum):
    """A named reason an Investigation is not finished.

    Named rather than a boolean so a stopped run can say *what* is missing.
    "Incomplete" tells an operator nothing they can act on.
    """

    #: Something the Board still does not know, at the priority that matters.
    #: The question the user asked is itself a HIGH-priority gap, so an
    #: unanswered question reports here rather than through a separate
    #: blocker — one representation, not two that can disagree.
    HIGH_PRIORITY_GAP_OPEN = "high_priority_gap_open"
    #: The Evaluator's independent recheck never agreed with the Analyst.
    EVIDENCE_UNVALIDATED = "evidence_unvalidated"
    #: Two measurements disagree and nobody has resolved or documented it.
    CONFLICT_UNSETTLED = "conflict_unsettled"
    #: No confidence recorded, or it sits below the Tenant's threshold.
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"


@dataclass(frozen=True, slots=True)
class CompletionAssessment:
    """What the loop concluded, and why."""

    blockers: tuple[CompletionBlocker, ...]
    budget_exhausted: bool

    @property
    def complete(self) -> bool:
        return not self.blockers

    @property
    def should_stop(self) -> bool:
        """Stop when finished, or when there is nothing left to finish with.

        Never on "the queue emptied" alone: that is a fact about scheduling,
        not about the question.
        """
        return self.complete or self.budget_exhausted

    def describe(self) -> str:
        """One line for the Board's narrative, safe to persist and display.

        Blocker names only — never a metric, a value, or a model's prose.
        This string reaches an operator surface, and the Board's narrative
        column is not an appropriate place for customer figures.
        """
        if self.complete:
            return "Complete: every completion criterion is satisfied."
        reasons = ", ".join(blocker.value for blocker in self.blockers)
        if self.budget_exhausted:
            return f"Stopped with budget exhausted; unsatisfied: {reasons}."
        return f"Incomplete; unsatisfied: {reasons}."


def assess_completion(
    board: InvestigationBoard,
    *,
    evidence_validated: bool,
    budget_exhausted: bool,
) -> CompletionAssessment:
    """Grade a Board against every completion criterion.

    Every criterion is checked, and all failures are reported — not the first
    one found. A run blocked on three things that reports one would be fixed
    three times.

    `evidence_validated` and `budget_exhausted` are arguments rather than Board
    state because neither is a property of what the Investigation *knows*: the
    first is what the Evaluator concluded about a particular measurement, and
    the second is what the loop was allowed to spend.
    """
    blockers: list[CompletionBlocker] = []
    if board.high_priority_open_gaps:
        blockers.append(CompletionBlocker.HIGH_PRIORITY_GAP_OPEN)
    if not evidence_validated:
        blockers.append(CompletionBlocker.EVIDENCE_UNVALIDATED)
    if board.unresolved_conflicts:
        blockers.append(CompletionBlocker.CONFLICT_UNSETTLED)
    if board.confidence is None or not board.confidence.meets_threshold:
        blockers.append(CompletionBlocker.CONFIDENCE_BELOW_THRESHOLD)
    return CompletionAssessment(
        blockers=tuple(blockers), budget_exhausted=budget_exhausted
    )
