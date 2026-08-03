"""Relations between Source Fields, and the Join Graph they form.

The safety property the whole connector turns on lives here: only a Relation a
human confirmed enters the Join Graph, and only the Join Graph is visible to
analytical agents.

    proposed --confirm--> confirmed --endpoint changed/dropped--> stale
       |                      ^                                     |
       |                      +-------------re-confirm--------------+
       +--reject--> rejected

    Join Graph := { r : r.state == confirmed }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .catalog import FieldIdentity
from .confidence import ConfidenceAssessment, OverlapMeasurement
from .types import (
    BindingCeiling,
    Cardinality,
    RejectionReason,
    RelationOrigin,
    RelationState,
    RelationTransitionError,
    StaleReason,
)


@dataclass(frozen=True, slots=True)
class RelationEvidence:
    """Why a Relation was proposed, in terms a reviewer can weigh.

    Every number a reviewer needs to disagree with the system is here. A
    proposal that could not be argued with would be an instruction, and the
    point of human confirmation is that it is a judgement.
    """

    name_affinity: float
    overlap_fraction: float
    sampled_rows: int
    left_distinct: int
    right_distinct: int
    matched_distinct: int
    raw_score: float
    sample_ceiling: float
    cardinality_ceiling: float

    @classmethod
    def build(
        cls,
        *,
        name_affinity: float,
        overlap: OverlapMeasurement,
        assessment: ConfidenceAssessment,
    ) -> RelationEvidence:
        return cls(
            name_affinity=round(name_affinity, 4),
            overlap_fraction=round(overlap.overlap_fraction, 4),
            sampled_rows=overlap.sampled_rows,
            left_distinct=overlap.left_distinct,
            right_distinct=overlap.right_distinct,
            matched_distinct=overlap.matched_distinct,
            raw_score=assessment.raw_score,
            sample_ceiling=assessment.sample_ceiling,
            cardinality_ceiling=assessment.cardinality_ceiling_value,
        )


def infer_cardinality(overlap: OverlapMeasurement) -> Cardinality:
    """State which side fans out, so a reviewer knows what joining will do.

    Uniqueness here is observed within a sample, never a constraint — ClickHouse
    has none to appeal to. ``UNKNOWN`` when neither side looks unique, which is
    a more useful answer than guessing ``MANY_TO_MANY`` at a reviewer.
    """
    if overlap.left_is_unique and overlap.right_is_unique:
        return Cardinality.ONE_TO_ONE
    if overlap.right_is_unique:
        return Cardinality.MANY_TO_ONE
    if overlap.left_is_unique:
        return Cardinality.ONE_TO_MANY
    return Cardinality.UNKNOWN


@dataclass(slots=True)
class Relation:
    """A proposed or confirmed join between two Source Fields.

    Pinned to ``left_identity``/``right_identity`` rather than to database row
    ids. That is what lets a confirmation survive a re-harvest that did not
    change the fields, and what makes one that *did* change them detectable.
    """

    relation_id: UUID
    tenant_id: UUID
    catalog_version_id: UUID
    left_field_id: UUID
    right_field_id: UUID
    left_identity: FieldIdentity
    right_identity: FieldIdentity
    left_data_source_id: UUID
    right_data_source_id: UUID
    state: RelationState
    origin: RelationOrigin
    confidence: float
    binding_ceiling: BindingCeiling
    cardinality: Cardinality
    evidence: RelationEvidence | None = None
    decided_at: datetime | None = None
    decided_by: UUID | None = None
    rejection_reason: RejectionReason | None = None
    stale_reason: StaleReason | None = None
    created_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_cross_source(self) -> bool:
        """Whether this Relation spans two Data Sources.

        Surfaced rather than derived by callers because it is the one property
        a reviewer most wants flagged: a join between an uploaded file and a
        warehouse is exactly the relationship no schema records.
        """
        return self.left_data_source_id != self.right_data_source_id

    @property
    def in_join_graph(self) -> bool:
        return self.state is RelationState.CONFIRMED

    @property
    def pinned_identities(self) -> frozenset[FieldIdentity]:
        return frozenset({self.left_identity, self.right_identity})

    def confirm(self, *, actor_id: UUID, at: datetime) -> None:
        """Admit this Relation to the Join Graph.

        Idempotent for a repeat of the same decision, so a double-clicked
        button cannot corrupt state. Refuses from ``rejected``: withdrawing a
        rejection is a different act from confirming a proposal, and silently
        conflating them would lose the reviewer's earlier judgement.
        """
        if self.state is RelationState.CONFIRMED:
            return
        if self.state not in (RelationState.PROPOSED, RelationState.STALE):
            raise RelationTransitionError(
                f"Cannot confirm a relation in state {self.state}"
            )
        self.state = RelationState.CONFIRMED
        self.decided_at = at
        self.decided_by = actor_id
        self.rejection_reason = None
        self.stale_reason = None

    def reject(
        self,
        *,
        actor_id: UUID,
        reason: RejectionReason,
        at: datetime,
    ) -> None:
        """Record that this Relation is wrong.

        Repeating an identical rejection is idempotent; rejecting with a
        *different* reason is a conflict rather than an update, because the
        recorded reason is what suppresses re-proposal and quietly rewriting it
        would change that behaviour without anyone deciding to.
        """
        if self.state is RelationState.REJECTED:
            if self.rejection_reason == reason:
                return
            raise RelationTransitionError(
                "Relation was already rejected for a different reason"
            )
        if self.state not in (RelationState.PROPOSED, RelationState.STALE):
            raise RelationTransitionError(
                f"Cannot reject a relation in state {self.state}"
            )
        self.state = RelationState.REJECTED
        self.decided_at = at
        self.decided_by = actor_id
        self.rejection_reason = reason

    def revoke(self, *, actor_id: UUID, at: datetime) -> None:
        """Withdraw a confirmation, returning the Relation to the queue."""
        if self.state is not RelationState.CONFIRMED:
            raise RelationTransitionError(
                f"Cannot revoke a relation in state {self.state}"
            )
        self.state = RelationState.PROPOSED
        self.decided_at = at
        self.decided_by = actor_id

    def mark_stale(self, *, reason: StaleReason, at: datetime) -> None:
        """Withdraw a Relation whose endpoints no longer hold.

        Only a confirmed Relation can go stale: an unconfirmed one was never in
        the Join Graph, so there is nothing to withdraw and re-proposing it
        against the new catalog is the honest treatment.
        """
        if self.state is not RelationState.CONFIRMED:
            raise RelationTransitionError(
                f"Cannot stale a relation in state {self.state}"
            )
        self.state = RelationState.STALE
        self.stale_reason = reason
        self.decided_at = at


@dataclass(frozen=True, slots=True)
class JoinGraph:
    """The confirmed Relations of one Catalog Version.

    The only thing an analytical agent may join on. Construction filters rather
    than trusting its caller, because a Join Graph that could be built holding a
    proposed Relation would make the guarantee a convention.
    """

    catalog_version_id: UUID
    relations: tuple[Relation, ...]

    @classmethod
    def build(
        cls,
        catalog_version_id: UUID,
        relations: tuple[Relation, ...],
    ) -> JoinGraph:
        return cls(
            catalog_version_id=catalog_version_id,
            relations=tuple(r for r in relations if r.in_join_graph),
        )

    def permits(self, left_field_id: UUID, right_field_id: UUID) -> bool:
        """Whether a join between these two fields is allowed.

        Order-insensitive: a Relation is a statement about a pair, and an agent
        writing the join the other way round is writing the same join.
        """
        pair = {left_field_id, right_field_id}
        return any({r.left_field_id, r.right_field_id} == pair for r in self.relations)

    def connected_field_ids(self) -> frozenset[UUID]:
        ids: set[UUID] = set()
        for relation in self.relations:
            ids.add(relation.left_field_id)
            ids.add(relation.right_field_id)
        return frozenset(ids)

    def isolated_field_ids(self, all_field_ids: frozenset[UUID]) -> frozenset[UUID]:
        """Fields that cannot be joined to anything.

        Worth surfacing: it is the difference between "your data connects" and
        "half your data is unreachable and nobody mentioned it".
        """
        return all_field_ids - self.connected_field_ids()

    @property
    def is_empty(self) -> bool:
        return not self.relations
