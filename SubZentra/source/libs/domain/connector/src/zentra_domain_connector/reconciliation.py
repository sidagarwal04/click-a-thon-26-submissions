"""Deciding what a re-harvest does to Relations a human already confirmed.

Two behaviours are wanted at once and they pull against each other. A routine
re-harvest must not force a reviewer to re-confirm work they already did. A
re-harvest that genuinely changed the schema must withdraw joins that may no
longer hold, because a confirmed Relation is a licence for an agent to join, and
a licence that outlives its subject is how a wrong Finding gets published.

Field identity is what resolves the tension: name, type and parent table
together. Unchanged on all three, the confirmation carries forward untouched.
Changed on any, it goes stale and waits for a human.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .catalog import CatalogVersion, FieldIdentity
from .relation import Relation
from .types import RelationState, StaleReason


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    """What happened to the previous version's Relations."""

    carried_forward: tuple[Relation, ...] = ()
    staled: tuple[Relation, ...] = ()
    suppressed_pairs: frozenset[frozenset[FieldIdentity]] = frozenset()

    @property
    def summary(self) -> dict[str, int]:
        return {
            "carried_forward": len(self.carried_forward),
            "staled": len(self.staled),
            "suppressed": len(self.suppressed_pairs),
        }


def _stale_reason(
    identity: FieldIdentity,
    current: CatalogVersion,
    index: dict[FieldIdentity, object],
) -> StaleReason | None:
    if identity in index:
        return None
    if identity.table_name not in current.table_names():
        return StaleReason.TABLE_DROPPED
    still_present = any(
        existing.table_name == identity.table_name
        and existing.field_name == identity.field_name
        for existing in index
    )
    # Present under the same name but a different normalised type is a type
    # change; absent entirely is a drop. Distinguished because they need
    # different things from the reviewer — one is "check this still means the
    # same thing", the other is "this is gone".
    if still_present:
        return StaleReason.FIELD_TYPE_CHANGED
    return StaleReason.FIELD_DROPPED


def reconcile(
    previous_relations: tuple[Relation, ...],
    current: CatalogVersion,
    *,
    new_catalog_version_id: UUID,
    at: datetime,
    new_field_ids: dict[FieldIdentity, UUID] | None = None,
) -> ReconciliationOutcome:
    """Carry confirmations forward onto a new Catalog Version, or stale them.

    Rejections are not carried forward as Relations — they are returned as
    ``suppressed_pairs`` so the caller can decline to re-propose them. A
    reviewer who rejected a guess should not be shown it again every week, but
    the rejection should also not clutter the Relation list forever.
    """
    index = current.field_index()
    ids = new_field_ids or {}
    carried: list[Relation] = []
    staled: list[Relation] = []
    suppressed: set[frozenset[FieldIdentity]] = set()

    for relation in previous_relations:
        if relation.state is RelationState.REJECTED:
            suppressed.add(relation.pinned_identities)
            continue
        if relation.state is not RelationState.CONFIRMED:
            # Proposals and already-stale relations belong to the version they
            # were computed against. The new run re-derives them from data
            # rather than inheriting a stale opinion of it.
            continue

        left_reason = _stale_reason(relation.left_identity, current, index)
        right_reason = _stale_reason(relation.right_identity, current, index)
        reason = left_reason or right_reason

        relation.catalog_version_id = new_catalog_version_id
        if reason is not None:
            relation.mark_stale(reason=reason, at=at)
            staled.append(relation)
            continue

        # Row ids change every harvest even when the field does not, so a
        # carried-forward Relation must be re-pointed at the new version's
        # fields or it would reference rows that no longer exist.
        left_id = ids.get(relation.left_identity)
        right_id = ids.get(relation.right_identity)
        if left_id is not None:
            relation.left_field_id = left_id
        if right_id is not None:
            relation.right_field_id = right_id
        carried.append(relation)

    return ReconciliationOutcome(
        carried_forward=tuple(carried),
        staled=tuple(staled),
        suppressed_pairs=frozenset(suppressed),
    )
