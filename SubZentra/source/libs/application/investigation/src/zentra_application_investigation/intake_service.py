"""Resolves a Thread message against the Tenant's Analytical Scope.

Replaces `thread_routing.py`'s keyword whitelist (ADR-0027). `IntakeService`
implements `IntakePort` by invoking an `AgentPort`-shaped Intake Agent — the
application layer depends only on that Protocol, never on a concrete
adapter, matching how `InvestigationPipeline` is wired.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import UUID

from zentra_domain_agent_execution import AgentInput, AgentPort, SemanticLayerPort

from .thread_dto import RoutingDisposition, RoutingResult

MAX_SCENARIO_KEY_LENGTH = 64
_DEFAULT_CLARIFICATION = (
    "I could not map that message to a question this catalog can answer. "
    "Please rephrase or add the detail (like a time period) needed to query it."
)


class IntakeService:
    """Builds a fresh Intake Agent per call, scoped to the caller's Tenant.

    Mirrors `LangGraphInvestigationPipeline`: an Agent that reads a semantic
    layer cannot be built once at startup and shared, because the layer
    itself is scoped per (Tenant, Data Connection) and resolved at request
    time (`ScopedCubeSemanticLayers`). The caller's resolved Data Connection is
    threaded through here so Intake sees the same catalog the Cube Analyst
    will later query — routing against a different one than the answer comes
    from is how "the catalog only has Commerce" gets said about a tenant whose
    connected source has never had a Commerce cube.
    """

    def __init__(
        self,
        *,
        agent_factory: Callable[[SemanticLayerPort], AgentPort],
        resolve_semantic_layer: Callable[
            [UUID, UUID | None], Awaitable[SemanticLayerPort]
        ],
        new_id: Callable[[], UUID],
    ) -> None:
        self._agent_factory = agent_factory
        self._resolve_semantic_layer = resolve_semantic_layer
        self._new_id = new_id

    async def resolve(
        self,
        question: str,
        *,
        tenant_id: UUID,
        data_connection_id: UUID | None = None,
    ) -> RoutingResult:
        semantic_layer = await self._resolve_semantic_layer(
            tenant_id, data_connection_id
        )
        agent = self._agent_factory(semantic_layer)
        output = await agent.invoke(
            AgentInput(
                # Intake precedes any Investigation; this id is discarded if
                # the message does not resolve, and reused as the real
                # Investigation id if it does (the caller's job, not ours).
                investigation_id=self._new_id(),
                tenant_id=tenant_id,
                state={"question": question},
            )
        )
        fields = output.fields
        disposition = str(fields.get("disposition", "unsupported"))
        normalized_question = fields.get("normalized_question")

        if disposition == "resolved" and normalized_question:
            canonical_question = str(normalized_question)
            return RoutingResult(
                disposition=RoutingDisposition.RESOLVED,
                scenario_key=_scenario_key(canonical_question),
                canonical_question=canonical_question,
                clarification=None,
                suggestions=(),
            )

        clarification = fields.get("clarification")
        return RoutingResult(
            disposition=(
                RoutingDisposition.AMBIGUOUS
                if disposition == "ambiguous"
                else RoutingDisposition.UNSUPPORTED
            ),
            scenario_key=None,
            canonical_question=None,
            clarification=str(clarification) if clarification else (
                _DEFAULT_CLARIFICATION
            ),
            suggestions=(),
        )


def _scenario_key(canonical_question: str) -> str:
    """A short, stable slug for `Investigation.scenario_key`.

    No longer a lookup key into a scenario whitelist (ADR-0027) — just a
    readable identifier derived from what Intake resolved, bounded to the
    column's width.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", canonical_question.casefold()).strip("_")
    return slug[:MAX_SCENARIO_KEY_LENGTH].rstrip("_") or "question"
