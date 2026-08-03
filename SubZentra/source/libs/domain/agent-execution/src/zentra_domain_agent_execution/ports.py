from __future__ import annotations

from collections.abc import Awaitable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import JsonValue

from .contracts import (
    AgentRole,
    ConfidenceOutcome,
    ExecutionUsage,
    OutcomeSignal,
    ToolInvocation,
)
from .tools import ToolCall, ToolDefinition, ToolResult

# ---------------------------------------------------------------------------
# Semantic layer
#
# This is the only port in the system that reaches data. `query()` enforces
# ADR-003's governed-catalog restriction; `query_raw()` deliberately does not,
# for tenants/agents that have opted out of it (still tenant-scoped — never
# cross-tenant).
# ---------------------------------------------------------------------------


class SemanticMeasure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    format: str | None = None
    # What this measure means in the tenant's own terms, carried from the
    # semantic model. A name tells an agent that `orders.revenue` exists; it
    # does not say whether that is gross or net of refunds, and choosing wrong
    # produces a confident answer to a different question.
    description: str | None = None


class SemanticDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    # The values this dimension actually holds, where there are few enough to
    # list. A member name alone tells an agent that `Commerce.region` exists
    # but not that it is spelled "NA" — and a filter on a value that does not
    # exist returns zero rows rather than an error. Empty means unconstrained,
    # not empty.
    values: tuple[str, ...] = ()
    # See SemanticMeasure.description.
    description: str | None = None


class SemanticCatalog(BaseModel):
    """The governed vocabulary an agent may reference. No physical schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measures: tuple[SemanticMeasure, ...]
    dimensions: tuple[SemanticDimension, ...]

    def member_names(self) -> frozenset[str]:
        return frozenset(
            [measure.name for measure in self.measures]
            + [dimension.name for dimension in self.dimensions]
        )

    def reject_ungoverned(self, request: SemanticQuery) -> None:
        """Refuse a query that reaches past the governed vocabulary.

        Every SemanticLayerPort implementation must call this before executing.
        A semantic-layer failure is a refusal; a raw-SQL failure is a
        confidently wrong number (ADR-003), and this is what keeps it the
        former.
        """
        referenced = set(request.measures) | set(request.dimensions)
        referenced.update(
            time_dimension.dimension for time_dimension in request.time_dimensions
        )
        referenced.update(semantic_filter.member for semantic_filter in request.filters)
        unknown = referenced - self.member_names()
        if unknown:
            raise UnknownSemanticMemberError(
                "Query references members outside the governed catalog: "
                + ", ".join(sorted(unknown))
            )


class SemanticTimeDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str = Field(min_length=1)
    granularity: str | None = None
    date_range: tuple[str, str] | None = None


class SemanticFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    member: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    values: tuple[str, ...] = ()


class SemanticQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    measures: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    time_dimensions: tuple[SemanticTimeDimension, ...] = ()
    filters: tuple[SemanticFilter, ...] = ()
    limit: int | None = Field(default=None, gt=0)


class SemanticResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: SemanticQuery
    rows: tuple[dict[str, JsonValue], ...] = ()


class UnknownSemanticMemberError(ValueError):
    """A query referenced a member the governed catalog does not define."""


class InvalidSemanticQueryError(ValueError):
    """The semantic layer refused a query built only from governed members.

    Naming every member correctly is not the same as asking something the
    layer can answer: a granularity a dimension does not support, or a filter
    operator it does not implement, is a well-formed request for an impossible
    result. Distinct from `UnknownSemanticMemberError` because the caller's
    correction is different — reshape the query, not rename its members — and
    distinct from a transport failure, which is not the caller's mistake at
    all and must not be reported to an Agent as though it were.
    """


class SemanticLayerPort(Protocol):
    def catalog(self) -> Awaitable[SemanticCatalog]: ...

    def query(self, request: SemanticQuery) -> Awaitable[SemanticResult]: ...

    # Same shape as `query`, but skips the governed-catalog rejection. Only
    # offered to an Agent whose tenant has opted out of ADR-003's restriction.
    def query_raw(self, request: SemanticQuery) -> Awaitable[SemanticResult]: ...


# ---------------------------------------------------------------------------
# Model provider
# ---------------------------------------------------------------------------


class ModelMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["user", "assistant"]
    content: str
    # A turn in a tool conversation. An assistant turn carries the calls it
    # asked for; the user turn that answers carries their results. Both are
    # needed because a provider will not accept a result for a call it cannot
    # see it made — the transcript has to be replayed whole on every round.
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    usage: ExecutionUsage
    # Rungs that failed before this one answered. Recorded even on success, so
    # Replay shows "Cerebras 402 -> NVIDIA 404 -> served by Gemini" rather than
    # silently showing Gemini.
    fallbacks: tuple[str, ...] = ()
    # Non-empty means the model wants tools run before it will answer. A
    # caller that passed no tools never sees these.
    tool_calls: tuple[ToolCall, ...] = ()
    # Why the model stopped. The runtime loop needs to tell "asked for a tool"
    # apart from "finished", and cannot infer it from an empty text block.
    stop_reason: str | None = None


def merged_fallbacks(*responses: ModelResponse) -> tuple[str, ...]:
    """Every rung that failed across the calls one agent made, in order.

    An agent makes several model calls, and each carries its own trail. Dropping
    all but the last would hide exactly the outage worth seeing.
    """
    seen: dict[str, None] = {}
    for response in responses:
        seen.update(dict.fromkeys(response.fallbacks))
    return tuple(seen)


class ModelPort(Protocol):
    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, JsonValue] | None = None,
        # Empty keeps the one-shot behaviour every existing caller relies on.
        # Non-empty offers the model these tools and may come back asking for
        # one, which only a caller prepared to run them should do.
        tools: Sequence[ToolDefinition] = (),
        # Low and fixed rather than left to provider defaults: this is a
        # trust-first system, and every agent's output is checked against
        # governed evidence either way, so there is nothing to gain from
        # sampling variance and a repeatable answer is easier to trust.
        temperature: float = 0.2,
    ) -> Awaitable[ModelResponse]: ...


# ---------------------------------------------------------------------------
# Agent executions
# ---------------------------------------------------------------------------


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    ESCALATED = "escalated"


class AgentExecutionRecord(BaseModel):
    """One bounded unit of agent work, scoped to a Tenant and Investigation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: UUID
    investigation_id: UUID
    tenant_id: UUID
    agent_id: str = Field(min_length=1)
    role: AgentRole
    step: int = Field(ge=0)
    input: dict[str, JsonValue]
    output: dict[str, JsonValue] | None = None
    outcome: OutcomeSignal | None = None
    status: ExecutionStatus
    latency_ms: int = Field(ge=0)
    usage: ExecutionUsage = ExecutionUsage()
    evidence_refs: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    fallbacks: tuple[str, ...] = ()
    # What the Agent actually did, in order. Names and timings only — never
    # arguments or results, which carry rows (ADR-0006). Without this, an
    # Agent that searched the catalog four times and queried twice is
    # indistinguishable in Replay from one that answered in a single shot.
    tool_calls: tuple[ToolInvocation, ...] = ()
    started_at: datetime
    completed_at: datetime

    @property
    def confidence(self) -> float | None:
        if isinstance(self.outcome, ConfidenceOutcome):
            return self.outcome.score
        return None


class AgentExecutionStart(BaseModel):
    """That an Agent Execution began, before anyone knows how it ends.

    Recorded separately because completion cannot describe a start. An agent
    that hangs, or a process killed mid-call, leaves no completion record at
    all — and Replay showing nothing is indistinguishable from the step never
    having been attempted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: UUID
    investigation_id: UUID
    tenant_id: UUID
    agent_id: str = Field(min_length=1)
    role: AgentRole
    step: int = Field(ge=0)
    started_at: datetime


class AgentExecutionRecorder(Protocol):
    """Persists a completed step before the next one starts, so an interrupted
    investigation still has a replayable trail of what already ran."""

    def record_started(self, start: AgentExecutionStart) -> Awaitable[None]: ...

    def record(self, execution: AgentExecutionRecord) -> Awaitable[None]: ...


# ---------------------------------------------------------------------------
# Agent registry (ADR-002: which agents exist is a table, never a code list)
# ---------------------------------------------------------------------------


class RegisteredAgent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1)
    role: AgentRole
    version: str = Field(min_length=1)


class AgentRegistryPort(Protocol):
    def enabled_agents(self) -> Awaitable[tuple[RegisteredAgent, ...]]: ...


# ---------------------------------------------------------------------------
# Sequence Step execution
#
# The operation itself is carried as a name + an unchecked parameter bag, not
# as zentra_domain_sequence's rich SequenceOperation type: sequence depends on
# agent-execution for this port, so agent-execution cannot depend back on
# sequence's catalog type without a cycle. zentra_domain_sequence is the one
# that knows how to validate/construct a SequenceOperation at this boundary.
# ---------------------------------------------------------------------------


class SequenceTableReference(BaseModel):
    """An opaque, tenant-scoped locator for a table a Sequence Step reads or
    produces — a Raw Table, or a prior Prepared Table."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    reference_id: UUID
    kind: Literal["raw", "prepared"]


class SequenceStepExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    sequence_id: UUID
    step_id: UUID
    operation_kind: str = Field(min_length=1)
    operation_parameters: dict[str, JsonValue]
    input_table: SequenceTableReference


class SequenceStepExecutionResult(BaseModel):
    """A Sequence Step applied successfully, producing a new table."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: SequenceStepExecutionRequest
    output_table: SequenceTableReference
    row_count: int = Field(ge=0)
    columns: tuple[str, ...]


class SequenceExecutionFailureReason(StrEnum):
    CATALOG_VIOLATION = "catalog_violation"
    DATA_INCOMPATIBLE = "data_incompatible"
    UNKNOWN_TABLE = "unknown_table"
    # An infrastructure-level failure (a Lambda invocation throttled, timed
    # out, or never returned) — distinct from the three above, which are all
    # about the operation or the data, not about reaching the executor.
    EXECUTION_ERROR = "execution_error"


class SequenceStepExecutionFailure(BaseModel):
    """A Sequence Step that could not be applied — a typed outcome, never a
    raw exception escaping the port boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: SequenceStepExecutionRequest
    reason: SequenceExecutionFailureReason
    detail: str = Field(min_length=1)


class SequenceExecutionPort(Protocol):
    def apply_operation(
        self, request: SequenceStepExecutionRequest
    ) -> Awaitable[SequenceStepExecutionResult | SequenceStepExecutionFailure]: ...
