"""Draft Finding persistence.

Its own module rather than another section of `investigation.py`, which is
already near the repository's 600-line limit.

Two tables, not a JSON blob on the Investigation, because claim order and the
observed/interpretation split have to survive as *queryable structure* — the
publication policy will read them, and Replay has to render them. A blob would
have made both a parsing exercise.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_agent_execution import OUTCOME_ADAPTER, ConfidenceOutcome
from zentra_domain_investigation import (
    CitationFilter,
    CitationState,
    Claim,
    ClaimKind,
    Contradiction,
    DeletionCategory,
    DraftFinding,
    EvidenceCitation,
    RootCauseState,
    Tombstone,
)

from .schema import (
    agent_executions,
    draft_finding_claim_citations,
    draft_finding_claims,
    draft_findings,
    erasure_operations,
    evidence_citations,
)


class PostgresDraftFindingRepository:
    """Tenant-scoped like every other repository here: the connection carries
    `app.tenant_id`, and RLS is what makes a cross-Tenant read return nothing
    rather than raise.
    """

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, draft: DraftFinding) -> None:
        confidence = draft.confidence
        await self._connection.execute(
            insert(draft_findings).values(
                draft_finding_id=draft.draft_finding_id,
                investigation_id=draft.investigation_id,
                tenant_id=draft.tenant_id,
                version=draft.version,
                produced_by_execution_id=draft.produced_by_execution_id,
                headline=draft.headline,
                summary=draft.summary,
                contradictions=[
                    {"detail": c.detail, "resolved": c.resolved}
                    for c in draft.contradictions
                ],
                root_cause=draft.root_cause.value,
                confidence=(
                    Decimal(str(confidence.score)) if confidence else None
                ),
                confidence_method=(
                    confidence.calibration_method if confidence else None
                ),
                created_at=draft.created_at,
            )
        )
        if not draft.claims:
            return
        await self._connection.execute(
            insert(draft_finding_claims),
            [
                {
                    "claim_id": claim.claim_id,
                    "draft_finding_id": draft.draft_finding_id,
                    "tenant_id": draft.tenant_id,
                    "kind": claim.kind.value,
                    "claim_text": claim.text,
                    "metric": claim.metric,
                    "claim_value": claim.value,
                    "period": claim.period,
                    "position": claim.position,
                }
                for claim in draft.claims
            ],
        )
        links = [
            {
                "claim_id": claim.claim_id,
                "citation_id": citation_id,
                "tenant_id": draft.tenant_id,
                "position": position,
            }
            for claim in draft.claims
            for position, citation_id in enumerate(claim.citation_ids)
        ]
        if links:
            await self._connection.execute(
                insert(draft_finding_claim_citations), links
            )

    async def latest_for_investigation(
        self,
        investigation_id: UUID,
    ) -> DraftFinding | None:
        """The current draft, which is the highest version.

        An Investigation can be evaluated up to three times, so it can hold
        more than one. Returning the latest is what makes a refresh show the
        same conclusion the reader saw, rather than the first attempt's.
        """
        row = (
            await self._connection.execute(
                select(draft_findings)
                .where(draft_findings.c.investigation_id == investigation_id)
                .order_by(draft_findings.c.version.desc())
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            return None

        claim_rows = (
            await self._connection.execute(
                select(draft_finding_claims)
                .where(
                    draft_finding_claims.c.draft_finding_id
                    == row.draft_finding_id
                )
                .order_by(draft_finding_claims.c.position)
            )
        ).all()

        # Read from the join, not from the claim's own JSON copy: the join is
        # what a citation is actually reachable through, so a divergence
        # between the two must surface as a missing citation rather than a
        # phantom one.
        link_rows = (
            await self._connection.execute(
                select(draft_finding_claim_citations)
                .where(
                    draft_finding_claim_citations.c.claim_id.in_(
                        [claim.claim_id for claim in claim_rows]
                    )
                )
                .order_by(draft_finding_claim_citations.c.position)
            )
        ).all()
        cited: dict[UUID, list[UUID]] = {}
        for link in link_rows:
            cited.setdefault(link.claim_id, []).append(link.citation_id)

        return DraftFinding(
            draft_finding_id=row.draft_finding_id,
            tenant_id=row.tenant_id,
            investigation_id=row.investigation_id,
            version=row.version,
            created_at=row.created_at,
            produced_by_execution_id=row.produced_by_execution_id,
            headline=row.headline,
            summary=row.summary,
            claims=tuple(
                Claim(
                    claim_id=claim.claim_id,
                    kind=ClaimKind(claim.kind),
                    text=claim.claim_text,
                    position=claim.position,
                    metric=claim.metric,
                    value=claim.claim_value,
                    period=claim.period,
                    citation_ids=tuple(cited.get(claim.claim_id, ())),
                )
                for claim in claim_rows
            ),
            contradictions=tuple(
                Contradiction(
                    detail=entry["detail"],
                    resolved=entry.get("resolved", False),
                )
                for entry in (row.contradictions or [])
            ),
            root_cause=RootCauseState(row.root_cause),
            confidence=(
                ConfidenceOutcome(
                    score=float(row.confidence),
                    calibration_method=row.confidence_method,
                )
                if row.confidence is not None
                else None
            ),
        )


class PostgresEvidenceCitationRepository:
    """Tenant-scoped like everything else here; RLS is what makes another
    Tenant's citation not exist rather than merely be filtered out."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, citations: Sequence[EvidenceCitation]) -> None:
        if not citations:
            return
        await self._connection.execute(
            insert(evidence_citations),
            [
                {
                    "citation_id": citation.citation_id,
                    "investigation_id": citation.investigation_id,
                    "tenant_id": citation.tenant_id,
                    "metric": citation.metric,
                    "filters": [
                        {
                            "member": f.member,
                            "operator": f.operator,
                            "values": list(f.values),
                        }
                        for f in citation.filters
                    ],
                    "period": citation.period,
                    "grain": citation.grain,
                    "producing_execution_id": citation.producing_execution_id,
                    "aggregate_value": citation.aggregate_value,
                    "evaluator_outcome": (
                        citation.evaluator_outcome.model_dump(mode="json")
                        if citation.evaluator_outcome
                        else None
                    ),
                    "state": citation.state.value,
                }
                for citation in citations
            ],
        )

    async def resolve(
        self,
        investigation_id: UUID,
        citation_id: UUID,
    ) -> EvidenceCitation | Tombstone | None:
        """One citation, with its state decided against the evidence itself.

        `None` means the citation is not visible to this connection — which
        covers "belongs to another Tenant", "belongs to another Investigation",
        and "does not exist". They must be indistinguishable: telling a caller
        which one applies confirms that somebody else's evidence exists.

        A citation whose producing execution is gone resolves `unavailable`.
        That is a fault, not a Tenant's deliberate erasure, so it is never
        reported as a Tombstone.
        """
        row = (
            await self._connection.execute(
                _resolvable().where(
                    evidence_citations.c.citation_id == citation_id,
                    evidence_citations.c.investigation_id == investigation_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        if row.resolved_state == CitationState.TOMBSTONED.value:
            # A Tombstone, not a blanked citation. Returning the row with its
            # values emptied would still hand back the metric, the period, the
            # grain and the filters — and a filter can carry customer values as
            # readily as an aggregate can.
            erasure = await self._erasure_record(investigation_id)
            return Tombstone(
                citation_id=row.citation_id,
                category=(
                    erasure[0]
                    if erasure
                    else DeletionCategory.TENANT_REQUEST.value
                ),
                erased_at=erasure[1] if erasure else row.created_at,
            )
        return _citation_from_row(row)

    async def _erasure_record(
        self, investigation_id: UUID
    ) -> tuple[str, datetime] | None:
        """The category and instant the Tombstone reports.

        Read from the erasure operation rather than inferred from the citation
        row, because *why* and *when* content went are facts about the deletion
        request, not about the thing deleted.
        """
        row = (
            await self._connection.execute(
                select(
                    erasure_operations.c.category,
                    erasure_operations.c.completed_at,
                )
                .where(
                    erasure_operations.c.investigation_id == investigation_id,
                    erasure_operations.c.completed_at.isnot(None),
                )
                .order_by(erasure_operations.c.completed_at.desc())
                .limit(1)
            )
        ).one_or_none()
        return (row.category, row.completed_at) if row is not None else None

    async def for_investigation(
        self,
        investigation_id: UUID,
    ) -> tuple[EvidenceCitation, ...]:
        """The same derivation the single-citation path uses.

        Two derivations would let one citation read `active` in the Draft
        Finding and `unavailable` when followed, having already shown the
        reader a figure the other surface says it cannot stand behind.
        """
        rows = (
            await self._connection.execute(
                _resolvable().where(
                    evidence_citations.c.investigation_id == investigation_id
                )
            )
        ).all()
        return tuple(_citation_from_row(row) for row in rows)


def _resolvable():
    """Citations, with `active` decided against the evidence itself.

    One LEFT JOIN rather than a follow-up query per citation: the state is a
    fact about whether the producing execution is still there, and asking once
    is both cheaper and impossible to get inconsistent between callers.

    `producing_execution_id` is `ON DELETE SET NULL`, and every citation is
    written with an execution, so a null one means loss rather than absence.
    """
    return select(
        evidence_citations,
        case(
            (
                and_(
                    evidence_citations.c.state == CitationState.ACTIVE.value,
                    agent_executions.c.execution_id.is_(None),
                ),
                CitationState.UNAVAILABLE.value,
            ),
            else_=evidence_citations.c.state,
        ).label("resolved_state"),
    ).select_from(
        evidence_citations.outerjoin(
            agent_executions,
            agent_executions.c.execution_id
            == evidence_citations.c.producing_execution_id,
        )
    )


def _citation_from_row(row: Any) -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=row.citation_id,
        tenant_id=row.tenant_id,
        investigation_id=row.investigation_id,
        metric=row.metric,
        filters=tuple(
            CitationFilter(
                member=item["member"],
                operator=item["operator"],
                values=tuple(item.get("values", [])),
            )
            for item in (row.filters or [])
        ),
        period=row.period,
        grain=row.grain,
        producing_execution_id=row.producing_execution_id,
        aggregate_value=row.aggregate_value,
        evaluator_outcome=(
            OUTCOME_ADAPTER.validate_python(row.evaluator_outcome)
            if row.evaluator_outcome
            else None
        ),
        # The derived state, not the stored one.
        state=CitationState(row.resolved_state),
    )
