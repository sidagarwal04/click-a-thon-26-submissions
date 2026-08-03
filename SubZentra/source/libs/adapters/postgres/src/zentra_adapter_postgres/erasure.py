"""Erasing an Investigation's evidence, coordinated.

Nine surfaces across four tables, in one transaction. One transaction is the
whole design: a partial erasure that committed would be content surviving a
deletion the operation could then call successful, and no retry would know
which half was left.

What is *not* here matters as much. Nothing touches ClickHouse — Audit Entries
are outside the mutation boundary by construction, not by discipline, and the
runtime's grants are insert/select anyway. Nothing drops a row: identity,
lifecycle, publication decisions and Human Approvals survive, because Replay
must still prove the work happened after its content is gone.

Internal until the user-facing workflow lands. Building it the other way round
means the first thing a Tenant can do is the thing that has never run.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    Text,
    cast,
    func,
    literal,
    null,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_investigation import (
    TERMINAL_STATUSES,
    DeletionCategory,
    ErasureOperation,
    ErasureProgress,
    EvidenceSurface,
    require_erasable,
)

from .schema import (
    agent_executions,
    draft_finding_claims,
    draft_findings,
    erasure_operations,
    evidence_citations,
    investigations,
)

TERMINAL = frozenset(status.value for status in TERMINAL_STATUSES)

#: What a value becomes. Not NULL: the column's shape is part of the process
#: record, and a reader following a Tombstone should find an erased value
#: rather than a missing column.
ERASED = ""


class ErasureIncompleteError(RuntimeError):
    """Content survived an erasure, so it did not succeed."""


class PostgresErasureRepository:
    """Tenant-scoped like everything else; RLS decides what is reachable."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def request(
        self,
        *,
        erasure_id: UUID,
        tenant_id: UUID,
        investigation_id: UUID,
        category: DeletionCategory,
        now: datetime,
    ) -> ErasureOperation:
        """Record the intent, refusing an Investigation that is still running.

        Idempotent: asking twice reaches the existing row rather than starting
        a second erasure that could race the first. A completed one is returned
        unchanged — re-erasing erased content is not an error, it is a no-op
        with an answer already.
        """
        status = await self._connection.scalar(
            select(investigations.c.status).where(
                investigations.c.investigation_id == investigation_id
            )
        )
        if status is None:
            raise LookupError("Investigation was not found")
        require_erasable(str(status), TERMINAL)

        existing = await self._get(investigation_id, category)
        if existing is not None:
            return existing

        await self._connection.execute(
            postgres_insert(erasure_operations)
            .values(
                erasure_id=erasure_id,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                category=category.value,
                progress=ErasureProgress.REQUESTED.value,
                requested_at=now,
                attempts=0,
            )
            # Two callers can both find no row; the constraint decides, and
            # the loser reads the winner's rather than raising.
            .on_conflict_do_nothing(constraint="uq_erasure_operations_request")
        )
        existing = await self._get(investigation_id, category)
        if existing is not None:
            return existing
        return ErasureOperation(
            erasure_id=erasure_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            category=category,
            progress=ErasureProgress.REQUESTED,
            requested_at=now,
        )

    async def erase(
        self,
        *,
        investigation_id: UUID,
        category: DeletionCategory,
        now: datetime,
    ) -> ErasureOperation:
        """Erase every surface, or leave the operation retryable.

        The caller's transaction is the boundary. If anything below raises, the
        whole thing rolls back and the operation stays un-completed — which is
        the only honest state for a deletion that did not finish.
        """
        operation = await self._get(investigation_id, category)
        if operation is None:
            raise LookupError("No erasure was requested for this Investigation")
        if operation.progress is ErasureProgress.COMPLETED:
            # Already done. Re-running would be harmless but would move the
            # completion time, and a Tombstone's timestamp should say when the
            # content actually went.
            return operation

        # Held for the rest of the transaction. A concurrent writer touching
        # this Investigation blocks rather than committing content after the
        # erasing UPDATE has already passed over its table.
        await self._connection.execute(
            select(investigations.c.investigation_id)
            .where(investigations.c.investigation_id == investigation_id)
            .with_for_update()
        )

        await self._connection.execute(
            update(erasure_operations)
            .where(erasure_operations.c.erasure_id == operation.erasure_id)
            .values(
                progress=ErasureProgress.ERASING.value,
                attempts=erasure_operations.c.attempts + 1,
                failure_code=None,
            )
        )

        for surface in EvidenceSurface:
            await self._erase_surface(surface, investigation_id)

        # Success is claimed only after checking. "We deleted some of it" is
        # the one answer this must never give, and the cheapest way to be sure
        # is to look rather than to assume the UPDATEs covered everything.
        remaining = await self._remaining_content(investigation_id)
        if remaining:
            # Names the surfaces, never their content: an operator has to
            # know which clause is failing, and nothing here quotes a value.
            raise ErasureIncompleteError(
                "Evidence survived the erasure on: "
                + ", ".join(surface.value for surface in remaining)
            )

        await self._connection.execute(
            update(erasure_operations)
            .where(erasure_operations.c.erasure_id == operation.erasure_id)
            .values(
                progress=ErasureProgress.COMPLETED.value,
                completed_at=now,
                failure_code=None,
            )
        )
        return await self._require(investigation_id, category)

    async def _erase_surface(
        self,
        surface: EvidenceSurface,
        investigation_id: UUID,
    ) -> None:
        """One surface. Driven off the enum so a surface added to the domain
        without a clause here fails loudly rather than being missed."""
        if surface is EvidenceSurface.AGENT_EXECUTION_INPUT:
            await self._connection.execute(
                update(agent_executions)
                .where(agent_executions.c.investigation_id == investigation_id)
                .values(input={})
            )
        elif surface is EvidenceSurface.AGENT_EXECUTION_OUTPUT:
            await self._connection.execute(
                update(agent_executions)
                # `null()`, not `None`: on a JSON column SQLAlchemy turns a
                # Python `None` into the JSON value `null`, which is a stored
                # document rather than an absent one.
                .where(agent_executions.c.investigation_id == investigation_id)
                .values(output=null())
            )
        elif surface is EvidenceSurface.INVESTIGATION_FINDING:
            # The narrative and its metric values go; the lifecycle, outcome
            # and publication decision in the same JSON stay.
            await self._connection.execute(
                update(investigations)
                .where(investigations.c.investigation_id == investigation_id)
                # `state` is `json`, not `jsonb`, so the key removal needs
                # an explicit round trip through `jsonb` and back.
                .values(
                    state=cast(
                        cast(investigations.c.state, JSONB).op("-")("finding"),
                        JSON,
                    )
                )
            )
        elif surface is EvidenceSurface.DRAFT_FINDING_NARRATIVE:
            await self._connection.execute(
                update(draft_findings)
                .where(draft_findings.c.investigation_id == investigation_id)
                .values(headline=ERASED, summary=ERASED)
            )
        elif surface is EvidenceSurface.DRAFT_FINDING_CLAIMS:
            await self._connection.execute(
                update(draft_finding_claims)
                .where(
                    draft_finding_claims.c.draft_finding_id.in_(
                        select(draft_findings.c.draft_finding_id).where(
                            draft_findings.c.investigation_id == investigation_id
                        )
                    )
                )
                # `kind` and `position` stay: that a claim was observed, and
                # where it sat, is process rather than content.
                #
                # `claim_value` is erased to empty rather than nulled, because
                # an observed claim must carry a measurement — the check
                # constraint that makes `observed` mean something would refuse
                # a null, and weakening it so evidence can be erased would
                # weaken it for every claim that is not.
                .values(claim_text=ERASED, claim_value=ERASED, period=None)
            )
        elif surface is EvidenceSurface.CITATION_AGGREGATE:
            await self._connection.execute(
                update(evidence_citations)
                .where(evidence_citations.c.investigation_id == investigation_id)
                # Tombstoned, not deleted: a claim must still resolve to
                # something that explains its own absence.
                #
                # The governed context goes with the value. A Tombstone carries
                # identity, category and instant — so leaving `metric`,
                # `period` and `grain` on the row would let the citation *list*
                # serve what resolving the same citation refuses.
                .values(
                    aggregate_value=ERASED,
                    state="tombstoned",
                    filters=[],
                    metric=ERASED,
                    period=None,
                    grain=None,
                )
            )
        elif surface is EvidenceSurface.DRAFT_FINDING_CONTRADICTIONS:
            await self._connection.execute(
                update(draft_findings)
                .where(draft_findings.c.investigation_id == investigation_id)
                .values(contradictions=[])
            )
        elif surface is EvidenceSurface.AGENT_EXECUTION_OUTCOME:
            # `outcome_kind` and `confidence` stay: that the step produced a
            # confidence, and what it was, is process. The outcome body is not
            # — a `ValidationOutcome` carries the Evaluator's issues verbatim.
            await self._connection.execute(
                update(agent_executions)
                .where(agent_executions.c.investigation_id == investigation_id)
                .values(outcome=null())
            )
        elif surface is EvidenceSurface.INVESTIGATION_FAILURE_MESSAGE:
            # The code stays and explains the terminal state; the message is
            # `str(error)` and can quote the erased value back.
            await self._connection.execute(
                update(investigations)
                .where(investigations.c.investigation_id == investigation_id)
                .values(
                    # `#-` takes a `text[]` path, not a jsonb value, so the
                    # literal has to say which it is.
                    state=cast(
                        cast(investigations.c.state, JSONB).op("#-")(
                            literal(["failure", "message"], ARRAY(Text))
                        ),
                        JSON,
                    )
                )
            )
        else:  # pragma: no cover - the enum is exhaustive above
            raise NotImplementedError(f"No erasure clause for {surface}")

    async def _remaining_content(
        self, investigation_id: UUID
    ) -> tuple[EvidenceSurface, ...]:
        """Which surfaces still hold something, after erasing them all."""
        draft_ids = select(draft_findings.c.draft_finding_id).where(
            draft_findings.c.investigation_id == investigation_id
        )
        checks: tuple[tuple[EvidenceSurface, object], ...] = (
            (
                EvidenceSurface.AGENT_EXECUTION_INPUT,
                select(func.count())
                .select_from(agent_executions)
                .where(
                    agent_executions.c.investigation_id == investigation_id,
                    cast(agent_executions.c.input, Text) != "{}",
                ),
            ),
            (
                EvidenceSurface.AGENT_EXECUTION_OUTPUT,
                select(func.count())
                .select_from(agent_executions)
                .where(
                    agent_executions.c.investigation_id == investigation_id,
                    agent_executions.c.output.isnot(None),
                ),
            ),
            (
                EvidenceSurface.AGENT_EXECUTION_OUTCOME,
                select(func.count())
                .select_from(agent_executions)
                .where(
                    agent_executions.c.investigation_id == investigation_id,
                    agent_executions.c.outcome.isnot(None),
                ),
            ),
            (
                EvidenceSurface.INVESTIGATION_FINDING,
                select(func.count())
                .select_from(investigations)
                .where(
                    investigations.c.investigation_id == investigation_id,
                    # `jsonb_exists` rather than the `?` operator: `?` is the
                    # driver's own placeholder and does not survive the round
                    # trip.
                    func.jsonb_exists(cast(investigations.c.state, JSONB), "finding"),
                ),
            ),
            (
                EvidenceSurface.DRAFT_FINDING_NARRATIVE,
                select(func.count())
                .select_from(draft_findings)
                .where(
                    draft_findings.c.investigation_id == investigation_id,
                    (draft_findings.c.headline != ERASED)
                    | (draft_findings.c.summary != ERASED),
                ),
            ),
            (
                EvidenceSurface.DRAFT_FINDING_CLAIMS,
                select(func.count())
                .select_from(draft_finding_claims)
                .where(
                    draft_finding_claims.c.draft_finding_id.in_(draft_ids),
                    (draft_finding_claims.c.claim_text != ERASED)
                    | (draft_finding_claims.c.claim_value != ERASED),
                ),
            ),
            (
                EvidenceSurface.CITATION_AGGREGATE,
                select(func.count())
                .select_from(evidence_citations)
                .where(
                    evidence_citations.c.investigation_id == investigation_id,
                    evidence_citations.c.aggregate_value != ERASED,
                ),
            ),
        )
        remaining = []
        for surface, statement in checks:
            if await self._connection.scalar(statement):
                remaining.append(surface)
        return tuple(remaining)

    async def _get(
        self,
        investigation_id: UUID,
        category: DeletionCategory,
    ) -> ErasureOperation | None:
        row = (
            await self._connection.execute(
                select(erasure_operations).where(
                    erasure_operations.c.investigation_id == investigation_id,
                    erasure_operations.c.category == category.value,
                )
            )
        ).one_or_none()
        return _operation_from_row(row) if row is not None else None

    async def _require(
        self,
        investigation_id: UUID,
        category: DeletionCategory,
    ) -> ErasureOperation:
        operation = await self._get(investigation_id, category)
        assert operation is not None
        return operation

    async def mark_failed(
        self,
        *,
        investigation_id: UUID,
        category: DeletionCategory,
        failure_code: str,
    ) -> None:
        """Record a category, never a message.

        Called from outside the failed transaction, so the erasure itself has
        already rolled back. The operation stays retryable — `failed` is a
        resting place, not a terminus.
        """
        await self._connection.execute(
            update(erasure_operations)
            .where(
                erasure_operations.c.investigation_id == investigation_id,
                erasure_operations.c.category == category.value,
                # Never un-complete a finished erasure. Content that is gone
                # does not come back because a later call failed.
                erasure_operations.c.progress != ErasureProgress.COMPLETED.value,
            )
            .values(
                progress=ErasureProgress.FAILED.value,
                failure_code=failure_code,
                completed_at=None,
            )
        )


def _operation_from_row(row: object) -> ErasureOperation:
    return ErasureOperation(
        erasure_id=row.erasure_id,
        tenant_id=row.tenant_id,
        investigation_id=row.investigation_id,
        category=DeletionCategory(row.category),
        progress=ErasureProgress(row.progress),
        requested_at=row.requested_at,
        completed_at=row.completed_at,
        attempts=row.attempts,
        failure_code=row.failure_code,
    )
