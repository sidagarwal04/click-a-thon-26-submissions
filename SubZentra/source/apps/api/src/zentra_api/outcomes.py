"""What a completed Investigation run established, before it becomes domain.

These three travelled with `InvestigationGraph` while LangGraph was the
mechanism (ADR-0026). They never depended on it — they are plain dataclasses —
and nothing inside the agent adapter reads them, so with the graph deleted they
belong beside their only consumer: the Orchestrator Loop that produces them and
the assembly that turns them into a `Finding`, a `DraftFinding`, and its
`EvidenceCitation`s.

Deliberately not domain objects. Assembling those is the application's job;
this module's job is to report what actually ran.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from zentra_domain_agent_execution import OutcomeSignal


@dataclass(slots=True)
class ValidatedEvidence:
    """One measurement the Analyst made and the Evaluator rechecked.

    Assembled from what actually ran — the Analyst's governed query, its
    result, and its execution id — so a Citation built from this cannot be a
    second account of the same claim. Insight's output has no part in it.
    """

    metric: str
    previous_value: str
    current_value: str
    previous_period: str | None
    current_period: str | None
    filters: tuple[dict[str, Any], ...]
    grain: str | None
    producing_execution_id: UUID


@dataclass(slots=True)
class InsightOutcome:
    """What the Insight Agent proposed, and who proposed it.

    Kept as one object rather than a spray of `insight_*` fields on
    `PipelineOutcome`: these travel together or not at all, and the execution
    id is the whole point — a Draft Finding has to name the Agent Execution
    that produced it.

    Deliberately not a `DraftFinding`. Assembling the domain object is the
    application's job; this is the report of what ran.
    """

    execution_id: UUID
    headline: str
    summary: str
    claims: list[dict[str, Any]]
    contradictions: tuple[str, ...]
    root_cause: str
    outcome: OutcomeSignal
    model: str | None
    fallbacks: tuple[str, ...]


@dataclass(slots=True)
class PipelineOutcome:
    """What the run established, for the application to act on."""

    headline: str
    summary: str
    metrics: list[dict[str, Any]]
    evidence_refs: tuple[str, ...]
    outcome: OutcomeSignal
    converged: bool
    contradictions: tuple[str, ...]
    attempts: int
    # Never absent: the loop raises rather than reaching the end without one.
    # Typed non-optional so the shape of the fallback this ticket removed
    # cannot quietly return.
    insight: InsightOutcome
    # What each agent's provider actually served. The application grades the
    # recheck's independence from these, so they must be the real model ids.
    analyst_model: str | None = None
    evaluator_model: str | None = None
    # Counted independently by each agent from its own query, so they can
    # legitimately differ; the application takes the lower and gates on a wide
    # divergence.
    analyst_sample_size: int | None = None
    evaluator_sample_size: int | None = None
    # What the Analyst measured, scoped how. Carried so Evidence Citations
    # can be built from validated state rather than from Insight's prose.
    evidence: tuple[ValidatedEvidence, ...] = ()
