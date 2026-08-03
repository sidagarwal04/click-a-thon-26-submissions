"""Evidence Citations: what a claim rests on, said in full.

An `artifact://execution/{id}` pointer says *where* the evidence lives and
nothing about what it is. A reader following one learns only that some agent
execution happened. ADR 0011 makes the Citation the user-facing contract
instead: the governed Semantic Metric, the filters, periods and grain that
scoped it, the Agent Execution that produced it, the validated aggregate, and
the Evaluator's verdict on it.

A Citation is never built from Insight's output. It is assembled from the state
the Cube Analyst and Evaluator already validated, which is what makes it
evidence rather than a second account of the same claim.

Citations are shared, not owned. Two claims about July's refunds rest on the
same measurement, and duplicating it would let the two drift. Order belongs to
the claim (`Claim.citation_ids`), not to the citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from zentra_domain_agent_execution import OutcomeSignal


class CitationState(StrEnum):
    """Whether the evidence behind a citation can still be reached.

    Three states, kept apart on purpose. `unavailable` is a fault — evidence
    that should be there and is not. `tombstoned` is a Tenant's deliberate
    erasure. Collapsing them would either alarm a reader about a deletion they
    asked for, or quietly reassure them about data loss.
    """

    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    TOMBSTONED = "tombstoned"


@dataclass(frozen=True, slots=True)
class CitationFilter:
    """One governed restriction the query carried.

    `values` are governed dimension members, not free text: the semantic layer
    rejects anything outside its catalog before a query runs.
    """

    member: str
    operator: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Tombstone:
    """What a citation resolves to once its evidence is deliberately erased.

    Identity, category, timestamp. Nothing else — not the metric, not the
    period, not the filters. A Tombstone exists to explain an absence without
    reconstructing what is absent, and a filter can carry customer values as
    readily as an aggregate can.

    Deliberately not a variant of `EvidenceCitation`: sharing the type would
    make it one field-add away from leaking the thing it was built to hide.
    """

    citation_id: UUID
    category: str
    erased_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    """One validated measurement, addressable on its own.

    Everything here comes from upstream state. `aggregate_value` is *copied*
    from the validated result rather than restated, so a Draft Finding's figure
    and its citation's figure cannot disagree.
    """

    citation_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    # The governed Semantic Metric, and how it was scoped.
    metric: str
    filters: tuple[CitationFilter, ...]
    period: str | None
    grain: str | None
    # Which Agent Execution produced it, and what the independent recheck made
    # of that execution's work.
    # Nullable because the execution row can be removed while the citation
    # outlives it; the column is `ON DELETE SET NULL` and the type has to
    # admit what the database allows.
    producing_execution_id: UUID | None
    aggregate_value: str
    evaluator_outcome: OutcomeSignal | None
    state: CitationState = CitationState.ACTIVE
