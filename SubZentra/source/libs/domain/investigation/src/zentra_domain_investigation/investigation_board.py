"""The durable object an Investigation accumulates its working memory onto.

See ADR-0026. Distinct from `workspace.py`'s `Group`/`Project` — those are
Tenant-visible navigation containers with no analytical content; the
Investigation Board is the shared canvas Work Items read and write for one
Investigation. The Orchestrator Loop decides what happens next by reading
this object, never by parsing an Agent's prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .model import EvidenceReference


class HypothesisStatus(StrEnum):
    OPEN = "open"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class GapPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DOCUMENTED = "documented"


@dataclass(frozen=True, slots=True)
class Fact:
    """One measurement a Work Item established, with its citation hook.

    Immutable once recorded — a Fact that turns out wrong is superseded by a
    new one and an opened Conflict, never edited in place, so Replay can show
    what the Board believed at each point.
    """

    fact_id: UUID
    metric: str
    value: str
    period: str | None
    producing_work_item_id: UUID
    evidence_refs: tuple[EvidenceReference, ...] = ()


@dataclass(slots=True)
class Hypothesis:
    hypothesis_id: UUID
    statement: str
    status: HypothesisStatus = HypothesisStatus.OPEN


@dataclass(slots=True)
class KnowledgeGap:
    """Something the Board does not yet know, with the priority an
    Orchestrator Loop uses to decide what to work on next."""

    gap_id: UUID
    description: str
    priority: GapPriority
    resolved: bool = False


@dataclass(slots=True)
class Conflict:
    """A contradiction between two Facts that must be resolved or
    explicitly documented before Insight may proceed."""

    conflict_id: UUID
    description: str
    status: ConflictStatus = ConflictStatus.OPEN
    resolution: str | None = None


@dataclass(frozen=True, slots=True)
class BoardConfidence:
    """The Board's current aggregate confidence, already bounded — never a
    raw model-reported score (ADR-0010)."""

    score: float | None
    threshold: float

    @property
    def meets_threshold(self) -> bool:
        return self.score is not None and self.score >= self.threshold


class BoardTransitionError(RuntimeError):
    pass


@dataclass(slots=True)
class InvestigationBoard:
    board_id: UUID
    investigation_id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    facts: list[Fact] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    gaps: list[KnowledgeGap] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    confidence: BoardConfidence | None = None
    narrative: str | None = None

    @classmethod
    def create(
        cls, *, board_id: UUID, investigation_id: UUID, tenant_id: UUID, now: datetime
    ) -> InvestigationBoard:
        return cls(
            board_id=board_id,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
        )

    @property
    def open_gaps(self) -> tuple[KnowledgeGap, ...]:
        return tuple(gap for gap in self.gaps if not gap.resolved)

    @property
    def high_priority_open_gaps(self) -> tuple[KnowledgeGap, ...]:
        return tuple(
            gap for gap in self.open_gaps if gap.priority is GapPriority.HIGH
        )

    @property
    def unresolved_conflicts(self) -> tuple[Conflict, ...]:
        return tuple(c for c in self.conflicts if c.status is ConflictStatus.OPEN)

    def contradicted_by(self, fact: Fact) -> Fact | None:
        """The Fact already on the Board that this one disagrees with.

        Two Work Items measuring the same metric over the same period must
        arrive at the same value; when they do not, one of them is wrong and
        the Board cannot silently keep both. Same metric and period with the
        *same* value is corroboration, not a contradiction — a fan-out that
        re-measures what the primary Analyst already measured is the cheapest
        confirmation available and must not read as a conflict.

        Returns the incumbent rather than opening the Conflict here: minting
        the `conflict_id` is the caller's job, as it is everywhere else in
        this domain.
        """
        for existing in self.facts:
            if (
                existing.metric == fact.metric
                and existing.period == fact.period
                and existing.value != fact.value
            ):
                return existing
        return None

    def record_fact(self, fact: Fact, *, now: datetime) -> None:
        self.facts.append(fact)
        self.updated_at = now

    def open_gap(self, gap: KnowledgeGap, *, now: datetime) -> None:
        self.gaps.append(gap)
        self.updated_at = now

    def resolve_gap(self, gap_id: UUID, *, now: datetime) -> None:
        gap = self._require_gap(gap_id)
        gap.resolved = True
        self.updated_at = now

    def open_hypothesis(self, hypothesis: Hypothesis, *, now: datetime) -> None:
        self.hypotheses.append(hypothesis)
        self.updated_at = now

    def settle_hypothesis(
        self, hypothesis_id: UUID, *, status: HypothesisStatus, now: datetime
    ) -> None:
        if status is HypothesisStatus.OPEN:
            raise BoardTransitionError("A Hypothesis cannot be settled back to open")
        hypothesis = self._require_hypothesis(hypothesis_id)
        hypothesis.status = status
        self.updated_at = now

    def open_conflict(self, conflict: Conflict, *, now: datetime) -> None:
        self.conflicts.append(conflict)
        self.updated_at = now

    def resolve_conflict(
        self,
        conflict_id: UUID,
        *,
        resolution: str,
        now: datetime,
        documented_only: bool = False,
    ) -> None:
        if not resolution.strip():
            raise ValueError("A Conflict resolution requires an explanation")
        conflict = self._require_conflict(conflict_id)
        conflict.status = (
            ConflictStatus.DOCUMENTED if documented_only else ConflictStatus.RESOLVED
        )
        conflict.resolution = resolution.strip()
        self.updated_at = now

    def set_confidence(self, confidence: BoardConfidence, *, now: datetime) -> None:
        self.confidence = confidence
        self.updated_at = now

    def set_narrative(self, narrative: str, *, now: datetime) -> None:
        self.narrative = narrative
        self.updated_at = now

    def _require_gap(self, gap_id: UUID) -> KnowledgeGap:
        for gap in self.gaps:
            if gap.gap_id == gap_id:
                return gap
        raise BoardTransitionError(f"Knowledge Gap {gap_id} is not on this Board")

    def _require_hypothesis(self, hypothesis_id: UUID) -> Hypothesis:
        for hypothesis in self.hypotheses:
            if hypothesis.hypothesis_id == hypothesis_id:
                return hypothesis
        raise BoardTransitionError(f"Hypothesis {hypothesis_id} is not on this Board")

    def _require_conflict(self, conflict_id: UUID) -> Conflict:
        for conflict in self.conflicts:
            if conflict.conflict_id == conflict_id:
                return conflict
        raise BoardTransitionError(f"Conflict {conflict_id} is not on this Board")
