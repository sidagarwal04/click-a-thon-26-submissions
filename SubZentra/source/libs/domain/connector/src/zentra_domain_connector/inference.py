"""Deciding which field pairs are worth measuring, and what the result means.

Split into two steps on purpose. Generating candidates is free and happens over
every pair; *measuring* one costs a query against someone's warehouse. So the
cheap signals gate the expensive one rather than running alongside it, and the
query budget is spent on pairs that already look plausible.

No model calls are involved anywhere here. Inference is deterministic, which is
what allows accuracy to be measured against TPC-H's documented foreign keys
rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .catalog import CatalogVersion, SourceField, SourceTable
from .confidence import OverlapMeasurement, assess
from .constants import MIN_OVERLAP_FRACTION, MIN_PROPOSAL_CONFIDENCE
from .naming import name_affinity
from .relation import RelationEvidence, infer_cardinality
from .types import Cardinality, TypeFamily
from .typing_rules import types_are_compatible


@dataclass(frozen=True, slots=True)
class CandidatePair:
    """Two fields worth spending a query on."""

    left_data_source_id: UUID
    left_table: SourceTable
    left_field: SourceField
    right_data_source_id: UUID
    right_table: SourceTable
    right_field: SourceField
    name_affinity: float

    @property
    def key(self) -> frozenset[UUID]:
        return frozenset({self.left_field.field_id, self.right_field.field_id})


#: What inference does *not* look for, stated so a reviewer is not misled.
#:
#: An empty proposal list is ambiguous on its own: it reads as "your data has no
#: relationships" when the truth may be "the relationships your data has are not
#: of a kind this looks for". Only single-field keys are considered, so a table
#: keyed on (tenant_id, order_id) yields nothing and looks like a table with no
#: relations at all. Saying so is the whole reason composite keys can honestly
#: be out of scope.
COMPOSITE_KEY_LIMITATION = (
    "Only single-field joins are considered. A table whose key spans two or "
    "more columns will not be proposed, and its absence here is not evidence "
    "that no relationship exists."
)


def coverage_summary(unexamined: tuple[UnexaminedField, ...]) -> dict[str, int]:
    """How many fields were skipped, grouped by why.

    Counts rather than the fields themselves: the point is to tell a reviewer
    the shape of what was not looked at, and a list of four hundred column names
    communicates less than "312 not a joinable type, 88 no counterpart found".
    """
    counts: dict[str, int] = {}
    for entry in unexamined:
        counts[entry.reason] = counts.get(entry.reason, 0) + 1
    return counts


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A measured candidate, ready to become a proposed Relation."""

    pair: CandidatePair
    confidence: float
    binding_ceiling: str
    cardinality: Cardinality
    evidence: RelationEvidence


@dataclass(frozen=True, slots=True)
class UnexaminedField:
    """A field that produced no candidates, and why.

    Reported so that "no relation found" is distinguishable from "never looked".
    A reviewer who cannot tell those apart will assume the wrong one.
    """

    field_id: UUID
    qualified_name: str
    reason: str


def _joinable(source_field: SourceField) -> tuple[bool, str]:
    if source_field.family is TypeFamily.FLOAT:
        return False, "float fields are not reliable join keys"
    if source_field.family is TypeFamily.TEMPORAL:
        return False, "temporal fields identify moments, not entities"
    if source_field.family is TypeFamily.BOOLEAN:
        return False, "boolean fields cannot identify anything"
    if source_field.family is TypeFamily.OTHER:
        return False, "unrecognised type family"
    return True, ""


def generate_candidates(
    catalogs: tuple[tuple[UUID, CatalogVersion], ...],
    *,
    min_name_affinity: float = 0.01,
) -> tuple[tuple[CandidatePair, ...], tuple[UnexaminedField, ...]]:
    """Find every field pair worth measuring, across all supplied catalogs.

    Takes a sequence of catalogs rather than one, because a pair spanning two
    Data Sources is the same problem as a pair within one. Building
    cross-source inference as a special case would have meant two code paths
    that could disagree.

    A field is paired with itself never, and with fields in its own table never
    — a column joining to its own table's neighbour is not a relation between
    entities, and including those would bury the real proposals in noise.
    """
    entries: list[tuple[UUID, SourceTable, SourceField]] = []
    unexamined: list[UnexaminedField] = []

    for data_source_id, catalog in catalogs:
        for table in catalog.tables:
            for source_field in table.fields:
                ok, reason = _joinable(source_field)
                if not ok:
                    unexamined.append(
                        UnexaminedField(
                            field_id=source_field.field_id,
                            qualified_name=f"{table.name}.{source_field.name}",
                            reason=reason,
                        )
                    )
                    continue
                entries.append((data_source_id, table, source_field))

    candidates: list[CandidatePair] = []
    paired: set[UUID] = set()

    for index, (left_source, left_table, left_field) in enumerate(entries):
        for right_source, right_table, right_field in entries[index + 1 :]:
            same_table = left_table.table_id == right_table.table_id
            if left_source == right_source and same_table:
                continue
            if not types_are_compatible(left_field.family, right_field.family):
                continue
            affinity = name_affinity(
                left_table.name, left_field.name, right_table.name, right_field.name
            )
            if affinity < min_name_affinity:
                continue
            candidates.append(
                CandidatePair(
                    left_data_source_id=left_source,
                    left_table=left_table,
                    left_field=left_field,
                    right_data_source_id=right_source,
                    right_table=right_table,
                    right_field=right_field,
                    name_affinity=affinity,
                )
            )
            paired.add(left_field.field_id)
            paired.add(right_field.field_id)

    for _, table, source_field in entries:
        if source_field.field_id not in paired:
            unexamined.append(
                UnexaminedField(
                    field_id=source_field.field_id,
                    qualified_name=f"{table.name}.{source_field.name}",
                    reason="no type-compatible, name-similar counterpart found",
                )
            )

    # Strongest names first, so that a run which exhausts its query budget has
    # spent it on the most promising pairs rather than on whatever came first.
    candidates.sort(key=lambda c: c.name_affinity, reverse=True)
    return tuple(candidates), tuple(unexamined)


def score_candidate(
    candidate: CandidatePair,
    overlap: OverlapMeasurement,
) -> ScoredCandidate | None:
    """Turn a measurement into a proposal, or decide it is not one.

    Returns ``None`` below either floor. A pair whose values mostly do not match
    is not a weak relation but a wrong one, and handing a reviewer a long list
    of wrong ones to reject individually is a worse failure than proposing
    nothing.
    """
    if overlap.overlap_fraction < MIN_OVERLAP_FRACTION:
        return None

    assessment = assess(name_affinity=candidate.name_affinity, overlap=overlap)
    if assessment.confidence < MIN_PROPOSAL_CONFIDENCE:
        return None

    return ScoredCandidate(
        pair=candidate,
        confidence=assessment.confidence,
        binding_ceiling=assessment.binding_ceiling,
        cardinality=infer_cardinality(overlap),
        evidence=RelationEvidence.build(
            name_affinity=candidate.name_affinity,
            overlap=overlap,
            assessment=assessment,
        ),
    )
