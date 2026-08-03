"""Deterministic Investigations for the browser journeys.

Written through the real repositories and real domain objects rather than as
SQL. The domain refuses an observed claim with no citation, an approval with no
failed conditions, a completed erasure with no timestamp; SQL would let every
one of those through, and a journey asserting against state the product could
never produce proves nothing about the product.

Fixed UUIDs, because #25 asks that "refresh and deep links reconstruct the same
Finding" — a deep link needs an id a spec can write down. Re-running replaces
what it made rather than accumulating, so a journey never sees two of anything.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from identity import tenant_id
from sqlalchemy import text
from zentra_adapter_postgres import Database
from zentra_adapter_postgres.investigation import (
    PostgresInvestigationUnitOfWorkFactory,
)
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    Claim,
    ClaimKind,
    Contradiction,
    DraftFinding,
    EvaluationDirective,
    EvidenceCitation,
    Finding,
    Investigation,
    MetricComparison,
    PublicationCondition,
    RootCauseState,
)
from zentra_domain_investigation.citation import CitationFilter, CitationState

_OUTPUT = Path(__file__).resolve().parents[2] / ".e2e"

#: Stable ids so a spec can deep-link without reading a file at runtime.
PUBLISHED = UUID("e2e00000-0000-4000-8000-000000000001")
GATED = UUID("e2e00000-0000-4000-8000-000000000002")
CONTRADICTED = UUID("e2e00000-0000-4000-8000-000000000003")

_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

#: Fixed, so a Replay timeline a journey asserts on is reproducible.
_TRACE_ID = UUID("e2e00000-0000-4000-8004-000000000001")
_SPAN_ID = UUID("e2e00000-0000-4000-8004-000000000002")


def _finding(headline: str, summary: str, metric: str, before: str, after: str) -> Finding:
    """The Phase 1 narrative Finding.

    Still required: the Observatory renders the Draft Finding *inside* the
    narrative one, so a fixture with claims but no `finding` shows nothing at
    all — which is how these fixtures first failed.
    """
    return Finding(
        headline=headline,
        summary=summary,
        metrics=(
            MetricComparison(
                metric=metric,
                previous_value=before,
                current_value=after,
                unit="ratio",
            ),
        ),
        evidence_refs=(),
    )


def _settle(
    investigation: Investigation,
    finding: Finding,
    confidence: ConfidenceOutcome,
    failed: tuple[PublicationCondition, ...],
) -> None:
    """Take the Investigation through evaluation, the way the pipeline does.

    Calling the aggregate's own transition rather than writing a terminal row
    keeps the lifecycle events real, so the Replay timeline a journey asserts
    on is one the product actually produces.
    """
    investigation.begin_evaluation(_NOW + timedelta(seconds=40))
    investigation.record_evaluation(
        directive=EvaluationDirective.PASS if not failed else EvaluationDirective.ESCALATE,
        outcome=confidence,
        finding=finding,
        now=_NOW + timedelta(seconds=50),
        failed_conditions=failed,
    )


def _claim(index: int, position: int, *, kind: ClaimKind, text: str, **extra) -> Claim:
    """`index` makes the id unique across drafts; `position` is per draft.

    They are separate because the domain requires positions contiguous from
    zero within one Draft Finding — a gap means a claim was lost — while ids
    have to stay distinct across all of them.
    """
    return Claim(
        claim_id=UUID(f"e2e00000-0000-4000-8001-{index:012d}"),
        kind=kind,
        text=text,
        position=position,
        **extra,
    )


def _citation(index: int, investigation: UUID, *, metric: str, value: str) -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=UUID(f"e2e00000-0000-4000-8002-{index:012d}"),
        tenant_id=tenant_id(),
        investigation_id=investigation,
        metric=metric,
        filters=(CitationFilter(member="Commerce.region", operator="equals", values=("EU",)),),
        period="2026-06-01/2026-07-01",
        grain="month",
        producing_execution_id=None,
        aggregate_value=value,
        evaluator_outcome=None,
        state=CitationState.ACTIVE,
    )


def _published() -> tuple[Investigation, DraftFinding, list[EvidenceCitation]]:
    """Every condition satisfied: cited, uncontradicted, converged, confident."""
    investigation = Investigation.create(
        investigation_id=PUBLISHED,
        tenant_id=tenant_id(),
        question="Why did EU refunds increase from June to July 2026?",
        now=_NOW,
    )
    investigation.start(_NOW + timedelta(seconds=1))
    citations = [
        _citation(1, PUBLISHED, metric="refund_rate", value="0.0412"),
        _citation(2, PUBLISHED, metric="refund_count", value="184"),
    ]
    draft = DraftFinding(
        draft_finding_id=UUID("e2e00000-0000-4000-8003-000000000001"),
        tenant_id=tenant_id(),
        investigation_id=PUBLISHED,
        version=1,
        created_at=_NOW + timedelta(seconds=30),
        produced_by_execution_id=None,
        headline="EU refund rate rose to 4.12% in June",
        summary=(
            "The refund rate for EU orders rose month over month. The evidence "
            "shows the change; it does not establish what caused it."
        ),
        claims=(
            _claim(
                1,
                0,
                kind=ClaimKind.OBSERVED,
                text="EU refund rate reached 4.12% in June 2026.",
                metric="refund_rate",
                value="0.0412",
                period="2026-06-01/2026-07-01",
                citation_ids=(citations[0].citation_id,),
            ),
            _claim(
                2,
                1,
                kind=ClaimKind.OBSERVED,
                text="184 EU orders were refunded in June 2026.",
                metric="refund_count",
                value="184",
                period="2026-06-01/2026-07-01",
                citation_ids=(citations[1].citation_id,),
            ),
            _claim(
                3,
                2,
                kind=ClaimKind.INTERPRETATION,
                text=(
                    "The increase is concentrated in a single month rather than "
                    "spread across the quarter."
                ),
            ),
        ),
        contradictions=(),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(score=0.82, calibration_method="evaluator_agreement"),
    )
    _settle(
        investigation,
        _finding(draft.headline, draft.summary, "refund_rate", "0.0301", "0.0412"),
        ConfidenceOutcome(score=0.82, calibration_method="evaluator_agreement"),
        (),
    )
    return investigation, draft, citations


def _gated() -> tuple[Investigation, DraftFinding, list[EvidenceCitation]]:
    """Held back: an observed claim whose only citation is unavailable."""
    investigation = Investigation.create(
        investigation_id=GATED,
        tenant_id=tenant_id(),
        question=(
            "Which sales channel accounted for the increase in North America "
            "revenue from October to November 2026?"
        ),
        now=_NOW,
    )
    investigation.start(_NOW + timedelta(seconds=1))
    citation = _citation(3, GATED, metric="revenue", value="128400")
    # Unavailable, not tombstoned: unexpected loss and a deliberate deletion are
    # different answers and criterion 7 requires they never be conflated.
    citation = EvidenceCitation(
        **{
            **{f: getattr(citation, f) for f in citation.__slots__},
            "state": CitationState.UNAVAILABLE,
        }
    )
    draft = DraftFinding(
        draft_finding_id=UUID("e2e00000-0000-4000-8003-000000000002"),
        tenant_id=tenant_id(),
        investigation_id=GATED,
        version=1,
        created_at=_NOW + timedelta(seconds=30),
        produced_by_execution_id=None,
        headline="North America revenue rose in November",
        summary="The supporting aggregate could not be resolved on re-read.",
        claims=(
            _claim(
                4,
                0,
                kind=ClaimKind.OBSERVED,
                text="North America revenue reached $128,400 in November 2026.",
                metric="revenue",
                value="128400",
                period="2026-11-01/2026-12-01",
                citation_ids=(citation.citation_id,),
            ),
        ),
        contradictions=(),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(score=0.55, calibration_method="evaluator_agreement"),
    )
    _settle(
        investigation,
        _finding(draft.headline, draft.summary, "revenue", "119200", "128400"),
        ConfidenceOutcome(score=0.55, calibration_method="evaluator_agreement"),
        (PublicationCondition.EVIDENCED, PublicationCondition.CONFIDENT),
    )
    return investigation, draft, [citation]


def _contradicted() -> tuple[Investigation, DraftFinding, list[EvidenceCitation]]:
    """Cited and confident, but the Evaluator disagreed and nobody resolved it."""
    investigation = Investigation.create(
        investigation_id=CONTRADICTED,
        tenant_id=tenant_id(),
        question="Why did EU refunds increase from June to July 2026?",
        now=_NOW,
    )
    investigation.start(_NOW + timedelta(seconds=1))
    citations = [_citation(4, CONTRADICTED, metric="refund_rate", value="0.0388")]
    draft = DraftFinding(
        draft_finding_id=UUID("e2e00000-0000-4000-8003-000000000003"),
        tenant_id=tenant_id(),
        investigation_id=CONTRADICTED,
        version=1,
        created_at=_NOW + timedelta(seconds=30),
        produced_by_execution_id=None,
        headline="EU refund rate rose to 3.88% in June",
        summary="The recheck disagreed with the first read and was not settled.",
        claims=(
            _claim(
                5,
                0,
                kind=ClaimKind.OBSERVED,
                text="EU refund rate reached 3.88% in June 2026.",
                metric="refund_rate",
                value="0.0388",
                period="2026-06-01/2026-07-01",
                citation_ids=(citations[0].citation_id,),
            ),
        ),
        contradictions=(
            Contradiction(
                detail=(
                    "The recheck measured 4.12% over the same period; the two "
                    "reads disagree and neither has been withdrawn."
                ),
            ),
        ),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(score=0.79, calibration_method="evaluator_agreement"),
    )
    _settle(
        investigation,
        _finding(draft.headline, draft.summary, "refund_rate", "0.0301", "0.0388"),
        ConfidenceOutcome(score=0.79, calibration_method="evaluator_agreement"),
        (PublicationCondition.UNCONTRADICTED,),
    )
    return investigation, draft, citations


async def _purge(database) -> None:
    """Remove anything an earlier run left, before writing it again.

    Deleting rather than upserting: a journey that saw two Draft Findings for
    one Investigation, or a claim from a previous shape of this file, would
    fail in a way that looks like a product bug. Restated on every run, the
    fixtures are whatever this file currently says and nothing else.

    Only the three fixed Investigation ids are touched. The bound identities
    are left alone — they are upserted by `bootstrap()` and shared.
    """
    async with database.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM investigations WHERE investigation_id = ANY(:ids)"),
            {"ids": [str(i) for i in (PUBLISHED, GATED, CONTRADICTED)]},
        )


async def seed() -> dict:
    database = Database(
        os.environ.get(
            "DATABASE_OWNER_URL",
            "postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control",
        )
    )
    await _purge(database)
    factory = PostgresInvestigationUnitOfWorkFactory(database)
    made: dict[str, str] = {}
    for name, build in (
        ("published", _published),
        ("gated", _gated),
        ("contradicted", _contradicted),
    ):
        investigation, draft, citations = build()
        async with factory(tenant_id(), _TRACE_ID, _SPAN_ID) as uow:
            await uow.investigations.add(investigation)
            # Citations before the draft: the claim/citation join has a foreign
            # key, so a draft written first cites rows that do not exist yet.
            if citations:
                await uow.citations.add(citations)
            await uow.draft_findings.add(draft)
            await uow.outbox.enqueue(investigation.events)
            await uow.commit()
        made[name] = str(investigation.investigation_id)
    await database.engine.dispose()
    return made


def main() -> int:
    made = asyncio.run(seed())
    _OUTPUT.mkdir(exist_ok=True)
    (_OUTPUT / "fixtures.json").write_text(json.dumps(made, indent=2))
    for name, identifier in made.items():
        print(f"{name:14} {identifier}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
