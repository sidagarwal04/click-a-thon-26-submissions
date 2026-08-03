"""The Draft Finding — what the Insight Agent proposes, before anything decides.

A Phase 1 `Finding` is narrative: a headline, a summary, and a bag of opaque
`artifact://` strings. Whether a sentence was measured or inferred, whether a
contradiction was still open, and whether causality was established at all were
all buried in prose that only a person could read.

Phase 2 needs those as data, because Replay has to *render* them and the
publication policy has to *decide* on them. Everything here exists to make one
of those two possible; nothing here decides whether a draft publishes. That is
the Investigation's deterministic policy, deliberately elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from zentra_domain_agent_execution import ConfidenceOutcome


class DraftFindingError(ValueError):
    """A Draft Finding was assembled in a shape a reviewer could not trust."""


class ClaimKind(StrEnum):
    """Whether a claim reports a measurement or an Agent's reading of one.

    The single most important distinction in the whole Draft Finding, and the
    one prose is least able to carry reliably.
    """

    OBSERVED = "observed"
    INTERPRETATION = "interpretation"


class RootCauseState(StrEnum):
    """Whether the evidence establishes why the observed change happened.

    One member, deliberately. ADR 0011 forbids a Root Cause Claim until a
    separate causal-evidence standard is accepted, so `unresolved` is the only
    honest answer Phase 2 can give. Modelling it as a state rather than as a
    missing field is what lets the product *say* "root cause unresolved"
    instead of quietly saying nothing.
    """

    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class Claim:
    """One substantive statement, and the evidence that backs it.

    An observed claim carries the measurement itself — the governed metric it
    rests on, the value, and the period that value covers — not just prose
    labelled `observed`. Without them a reader is asked to take the label on
    trust, and "distinguish evidence from interpretation" becomes a claim about
    formatting rather than about evidence.

    They are optional because an interpretation legitimately has no measurement
    of its own; `DraftFinding` is what refuses an observed claim missing one.

    `citation_ids` is empty until Evidence Citations exist. The field is here
    now so that adding them is a write, not a schema migration.
    """

    claim_id: UUID
    kind: ClaimKind
    text: str
    position: int
    metric: str | None = None
    value: str | None = None
    period: str | None = None
    citation_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class Contradiction:
    """An Evaluator disagreement that synthesis must not smooth away."""

    detail: str
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class DraftFinding:
    """An unpublished conclusion, owned by one Tenant and one Investigation."""

    draft_finding_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    version: int
    created_at: datetime
    # The Insight Agent Execution that produced it. Optional only during the
    # migration window: Insight does not run yet, and a draft that predates it
    # has no execution to point at.
    produced_by_execution_id: UUID | None
    headline: str
    summary: str
    claims: tuple[Claim, ...]
    contradictions: tuple[Contradiction, ...]
    root_cause: RootCauseState
    # Already bounded by the application's independence and sample-size
    # ceilings, and carrying the name of whichever bound won. Insight does not
    # get to score itself past what its evidence allows.
    confidence: ConfidenceOutcome | None

    def __post_init__(self) -> None:
        positions = sorted(claim.position for claim in self.claims)
        if positions != list(range(len(self.claims))):
            raise DraftFindingError(
                "Claim positions must be contiguous from zero; a gap or a "
                f"duplicate means a claim was lost. Got {positions}."
            )
        for claim in self.claims:
            if claim.kind is not ClaimKind.OBSERVED:
                continue
            if not claim.metric or claim.value is None:
                # An observed claim with no measurement is an interpretation
                # wearing the wrong label, which is the one confusion this
                # whole type exists to prevent.
                #
                # `is None`, not falsiness: erasure empties a value while
                # leaving the field. Rejecting an empty string would make every
                # Investigation whose evidence a Tenant deleted permanently
                # unreadable — the draft would raise on load, so the deletion
                # would destroy the process record it was supposed to preserve.
                raise DraftFindingError(
                    f"Claim {claim.position} is observed but carries no "
                    f"measurement"
                )
            if not claim.citation_ids:
                # A substantive claim a reader cannot follow to its evidence is
                # the thing Phase 2 exists to stop shipping.
                raise DraftFindingError(
                    f"Claim {claim.position} is observed but cites no evidence"
                )
