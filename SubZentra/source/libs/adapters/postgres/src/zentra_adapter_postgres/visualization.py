from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_investigation import (
    VisualizationActionKind,
    VisualizationActionMapping,
    VisualizationArtifact,
    VisualizationArtifactStatus,
    VisualizationBriefV1,
    VisualizationUsage,
)

from .schema import (
    visualization_actions,
    visualization_artifacts,
    visualization_briefs,
)


def _artifact(row: Any) -> VisualizationArtifact:
    return VisualizationArtifact(
        visualization_id=row.visualization_id,
        tenant_id=row.tenant_id,
        investigation_id=row.investigation_id,
        brief_id=row.brief_id,
        status=VisualizationArtifactStatus(row.status),
        renderer_kind=row.renderer_kind,
        model=row.model,
        api_version=row.api_version,
        c1_response=row.c1_response,
        usage=VisualizationUsage(
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cost_usd=Decimal(row.cost_usd),
            latency_ms=row.latency_ms,
        ),
        failure_category=row.failure_category,
        retry_of_visualization_id=row.retry_of_visualization_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        erased_at=row.erased_at,
        erasure_category=row.erasure_category,
    )


def _action(row: Any) -> VisualizationActionMapping:
    return VisualizationActionMapping(
        action_id=row.action_id,
        tenant_id=row.tenant_id,
        visualization_id=row.visualization_id,
        thread_id=row.thread_id,
        investigation_id=row.investigation_id,
        kind=VisualizationActionKind(row.kind),
        label=row.label,
        citation_id=row.citation_id,
        follow_up_message=row.follow_up_message,
        expires_at=row.expires_at,
        single_use=bool(row.single_use),
        consumed_at=row.consumed_at,
    )


class PostgresVisualizationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def create(
        self,
        *,
        brief_id: UUID,
        brief: VisualizationBriefV1,
        renderer_configuration: str,
        artifact: VisualizationArtifact,
        actions: tuple[VisualizationActionMapping, ...],
    ) -> None:
        await self._connection.execute(
            insert(visualization_briefs).values(
                brief_id=brief_id,
                tenant_id=artifact.tenant_id,
                investigation_id=artifact.investigation_id,
                schema_version=brief.schema_version,
                content=brief.model_dump(mode="json"),
                content_hash=brief.content_hash(
                    renderer_configuration=renderer_configuration
                ),
                renderer_configuration=renderer_configuration,
                created_at=artifact.created_at,
            )
        )
        await self._connection.execute(
            insert(visualization_artifacts).values(
                visualization_id=artifact.visualization_id,
                tenant_id=artifact.tenant_id,
                investigation_id=artifact.investigation_id,
                brief_id=brief_id,
                status=artifact.status.value,
                renderer_kind=artifact.renderer_kind,
                retry_of_visualization_id=artifact.retry_of_visualization_id,
                retry_ordinal=0,
                created_at=artifact.created_at,
                updated_at=artifact.updated_at,
            )
        )
        if actions:
            await self._connection.execute(
                insert(visualization_actions),
                [
                    {
                        **value.model_dump(mode="python"),
                        "kind": value.kind.value,
                        "single_use": int(value.single_use),
                        "created_at": artifact.created_at,
                    }
                    for value in actions
                ],
            )

    async def add_retry(
        self, artifact: VisualizationArtifact, *, retry_ordinal: int
    ) -> None:
        await self._connection.execute(
            insert(visualization_artifacts).values(
                visualization_id=artifact.visualization_id,
                tenant_id=artifact.tenant_id,
                investigation_id=artifact.investigation_id,
                brief_id=artifact.brief_id,
                status=artifact.status.value,
                renderer_kind=artifact.renderer_kind,
                retry_of_visualization_id=artifact.retry_of_visualization_id,
                retry_ordinal=retry_ordinal,
                created_at=artifact.created_at,
                updated_at=artifact.updated_at,
            )
        )

    async def brief(self, brief_id: UUID) -> VisualizationBriefV1 | None:
        content = (
            await self._connection.execute(
                select(visualization_briefs.c.content).where(
                    visualization_briefs.c.brief_id == brief_id
                )
            )
        ).scalar_one_or_none()
        return VisualizationBriefV1.model_validate(content) if content else None

    async def get(
        self, visualization_id: UUID, *, for_update: bool = False
    ) -> VisualizationArtifact | None:
        statement = select(visualization_artifacts).where(
            visualization_artifacts.c.visualization_id == visualization_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).one_or_none()
        return _artifact(row) if row else None

    async def latest_for_investigation(
        self, investigation_id: UUID
    ) -> VisualizationArtifact | None:
        row = (
            await self._connection.execute(
                select(visualization_artifacts)
                .where(visualization_artifacts.c.investigation_id == investigation_id)
                .order_by(
                    visualization_artifacts.c.retry_ordinal.desc(),
                    visualization_artifacts.c.created_at.desc(),
                )
                .limit(1)
            )
        ).one_or_none()
        return _artifact(row) if row else None

    async def next_retry_ordinal(self, brief_id: UUID) -> int:
        value = (
            await self._connection.execute(
                select(func.max(visualization_artifacts.c.retry_ordinal)).where(
                    visualization_artifacts.c.brief_id == brief_id
                )
            )
        ).scalar_one()
        return int(value or 0) + 1

    async def save(self, artifact: VisualizationArtifact) -> None:
        await self._connection.execute(
            update(visualization_artifacts)
            .where(
                visualization_artifacts.c.visualization_id == artifact.visualization_id
            )
            .values(
                status=artifact.status.value,
                model=artifact.model,
                api_version=artifact.api_version,
                c1_response=artifact.c1_response,
                input_tokens=artifact.usage.input_tokens,
                output_tokens=artifact.usage.output_tokens,
                cost_usd=artifact.usage.cost_usd,
                latency_ms=artifact.usage.latency_ms,
                failure_category=artifact.failure_category,
                updated_at=artifact.updated_at,
                erased_at=artifact.erased_at,
                erasure_category=artifact.erasure_category,
            )
        )

    async def action(
        self, visualization_id: UUID, action_id: UUID, *, for_update: bool = False
    ) -> VisualizationActionMapping | None:
        statement = select(visualization_actions).where(
            visualization_actions.c.visualization_id == visualization_id,
            visualization_actions.c.action_id == action_id,
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).one_or_none()
        return _action(row) if row else None

    async def save_action(self, action: VisualizationActionMapping) -> None:
        await self._connection.execute(
            update(visualization_actions)
            .where(visualization_actions.c.action_id == action.action_id)
            .values(consumed_at=action.consumed_at)
        )

    async def erase(self, investigation_id: UUID, *, category: str, now: Any) -> None:
        artifact_ids = select(visualization_artifacts.c.visualization_id).where(
            visualization_artifacts.c.investigation_id == investigation_id
        )
        await self._connection.execute(
            delete(visualization_actions).where(
                visualization_actions.c.visualization_id.in_(artifact_ids)
            )
        )
        await self._connection.execute(
            update(visualization_briefs)
            .where(visualization_briefs.c.investigation_id == investigation_id)
            .values(content=None)
        )
        await self._connection.execute(
            update(visualization_artifacts)
            .where(visualization_artifacts.c.investigation_id == investigation_id)
            .values(
                c1_response=None,
                status=case(
                    (
                        visualization_artifacts.c.status
                        == VisualizationArtifactStatus.READY.value,
                        VisualizationArtifactStatus.TOMBSTONED.value,
                    ),
                    else_=visualization_artifacts.c.status,
                ),
                erased_at=case(
                    (
                        visualization_artifacts.c.status
                        == VisualizationArtifactStatus.READY.value,
                        now,
                    ),
                    else_=visualization_artifacts.c.erased_at,
                ),
                erasure_category=case(
                    (
                        visualization_artifacts.c.status
                        == VisualizationArtifactStatus.READY.value,
                        category,
                    ),
                    else_=visualization_artifacts.c.erasure_category,
                ),
                updated_at=now,
            )
        )
