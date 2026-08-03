"""Erasing evidence, as an operation rather than a delete statement.

A Tenant asking for their evidence to be erased is asking for something that
touches nine surfaces across four tables, must survive a crash halfway
through,
and must never report success while any of it remains. That is an operation
with a lifecycle, not a statement.

Nothing here is reachable by a Tenant. This is the prefactor: the shape and the
guarantees land first, and the user-facing workflow that invokes them lands
separately. Building it the other way round means the first thing a Tenant can
do is the thing that has never been exercised.

Two invariants carry most of the weight. A partial failure is never a success —
"we deleted some of it" is the one answer this must never give. And Audit
Entries are outside the boundary entirely: Replay must still prove the work
happened after its content is gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ErasureError(ValueError):
    """An erasure was asked for in a state that cannot honour it."""


class DeletionCategory(StrEnum):
    """Why the content went.

    Recorded because a Tombstone must be able to say *that* it was deliberate
    without saying what was erased. One member today: inventing categories no
    caller can produce would put words in a future Tenant's mouth.
    """

    TENANT_REQUEST = "tenant_request"


class ErasureProgress(StrEnum):
    """Where an operation got to.

    `failed` is a resting place, not a terminus — a partial erasure is
    retryable, and the one thing it must never be is `completed`.
    """

    REQUESTED = "requested"
    ERASING = "erasing"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceSurface(StrEnum):
    """Every place a Tenant's evidence or its derivatives can be.

    Enumerated rather than described, so "did we get all of it?" has an answer
    a test can check. A surface added to the schema and not to this list is a
    surface an erasure silently misses, which is why the integration harness
    walks this enum rather than a hand-written list of columns.
    """

    #: What an Agent was given, including the question and upstream state.
    AGENT_EXECUTION_INPUT = "agent_execution_input"
    #: What it produced, including result rows.
    AGENT_EXECUTION_OUTPUT = "agent_execution_output"
    #: The Phase 1 narrative Finding, inside `investigations.state`.
    INVESTIGATION_FINDING = "investigation_finding"
    #: A Draft Finding's headline and summary.
    DRAFT_FINDING_NARRATIVE = "draft_finding_narrative"
    #: Claim text and the measured values it carries.
    DRAFT_FINDING_CLAIMS = "draft_finding_claims"
    #: The validated aggregate a citation resolves to.
    CITATION_AGGREGATE = "citation_aggregate"
    #: A Draft Finding's contradictions — Evaluator prose, derived from the
    #: data as much as any claim is.
    DRAFT_FINDING_CONTRADICTIONS = "draft_finding_contradictions"
    #: An Agent Execution's typed outcome. A `ValidationOutcome` carries the
    #: Evaluator's issues verbatim, so the outcome is content, not just shape.
    AGENT_EXECUTION_OUTCOME = "agent_execution_outcome"
    #: A pipeline failure records `str(error)`, which can quote the very value
    #: being erased back at the reader.
    INVESTIGATION_FAILURE_MESSAGE = "investigation_failure_message"


#: Not a surface, and said so rather than left looking covered: this system
#: has no cached-response store. The only cache is the in-process Semantic
#: catalog, which holds governed metric definitions and no Tenant data. If one
#: is ever introduced it belongs in `EvidenceSurface` above.
NO_CACHED_RESPONSE_STORE = True

#: What survives, and must. Named here rather than left implicit, because the
#: whole point of erasing content instead of rows is that Replay can still
#: prove the work happened.
PRESERVED = (
    "Investigation identity and lifecycle transitions",
    "Publication decisions and their failed conditions",
    "Human Approval decisions and their reasons",
    "Non-sensitive Agent Execution metadata: agent, model, timings, usage",
    "Immutable Audit Entries, which are outside the mutation boundary",
)


@dataclass(frozen=True, slots=True)
class ErasureOperation:
    """One request to erase one Investigation's evidence."""

    erasure_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    category: DeletionCategory
    progress: ErasureProgress
    requested_at: datetime
    completed_at: datetime | None = None
    attempts: int = 0
    #: A category, never a message. An erasure's failure must not become the
    #: place the erased value is quoted back.
    failure_code: str | None = None

    def __post_init__(self) -> None:
        completed = self.progress is ErasureProgress.COMPLETED
        if completed and self.completed_at is None:
            raise ErasureError("A completed erasure must record when it completed")
        if not completed and self.completed_at is not None:
            raise ErasureError("Only a completed erasure may record a completion time")
        if self.progress is ErasureProgress.FAILED and self.failure_code is None:
            raise ErasureError("A failed erasure must record why")

    @property
    def is_settled(self) -> bool:
        """Whether this operation still has work to do.

        `failed` is not settled: a partial erasure is retryable, and treating
        it as finished is how content survives a deletion that reported
        success.
        """
        return self.progress is ErasureProgress.COMPLETED


def require_erasable(status: str, terminal: frozenset[str]) -> None:
    """Refuse an Investigation that is still running.

    Erasing under a live pipeline races every write still to come, and the
    Agent Executions it has not finished would reintroduce exactly what was
    erased.
    """
    if status not in terminal:
        raise ErasureError(
            f"Evidence can only be erased from a terminal Investigation; "
            f"this one is {status}"
        )
