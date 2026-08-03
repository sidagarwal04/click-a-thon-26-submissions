from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_application_investigation import (
    OrganizationCursor,
    OrganizationNameConflictError,
    OrganizationSlice,
)
from zentra_domain_investigation import Group, Project

from .database import Database, set_tenant_context
from .schema import projects, workspace_groups

_NAME_CONSTRAINTS = frozenset(
    {"uq_workspace_groups_tenant_name", "uq_projects_group_name"}
)


def _translate_integrity(error: IntegrityError) -> None:
    diagnostic = getattr(error.orig, "diag", None)
    if getattr(diagnostic, "constraint_name", None) in _NAME_CONSTRAINTS:
        raise OrganizationNameConflictError(
            "A workspace with this name already exists in its parent"
        ) from error
    raise error


def _group_from_row(row: Any) -> Group:
    value = row._mapping
    return Group(
        group_id=value["group_id"],
        tenant_id=value["tenant_id"],
        name=value["name"],
        normalized_name=value["normalized_name"],
        created_at=value["created_at"],
        updated_at=value["updated_at"],
        archived_at=value["archived_at"],
    )


def _project_from_row(row: Any) -> Project:
    value = row._mapping
    return Project(
        project_id=value["project_id"],
        tenant_id=value["tenant_id"],
        group_id=value["group_id"],
        name=value["name"],
        normalized_name=value["normalized_name"],
        created_at=value["created_at"],
        updated_at=value["updated_at"],
        latest_activity_at=value["latest_activity_at"],
        archived_at=value["archived_at"],
    )


class PostgresOrganizationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_group(self, group: Group) -> None:
        try:
            await self._connection.execute(
                insert(workspace_groups).values(
                    group_id=group.group_id,
                    tenant_id=group.tenant_id,
                    name=group.name,
                    normalized_name=group.normalized_name,
                    created_at=group.created_at,
                    updated_at=group.updated_at,
                    archived_at=group.archived_at,
                )
            )
        except IntegrityError as error:
            _translate_integrity(error)

    async def get_group(
        self, group_id: UUID, *, for_update: bool = False
    ) -> Group | None:
        statement = select(workspace_groups).where(
            workspace_groups.c.group_id == group_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).first()
        return _group_from_row(row) if row is not None else None

    async def save_group(self, group: Group) -> None:
        try:
            await self._connection.execute(
                update(workspace_groups)
                .where(workspace_groups.c.group_id == group.group_id)
                .values(
                    name=group.name,
                    normalized_name=group.normalized_name,
                    updated_at=group.updated_at,
                    archived_at=group.archived_at,
                )
            )
        except IntegrityError as error:
            _translate_integrity(error)

    async def list_groups(
        self,
        *,
        include_archived: bool,
        limit: int,
        after: OrganizationCursor | None,
    ) -> OrganizationSlice[Group]:
        statement = select(workspace_groups)
        if not include_archived:
            statement = statement.where(workspace_groups.c.archived_at.is_(None))
        if after is not None:
            statement = statement.where(
                tuple_(workspace_groups.c.updated_at, workspace_groups.c.group_id)
                < tuple_(after.sort_at, after.resource_id)
            )
        statement = statement.order_by(
            workspace_groups.c.updated_at.desc(), workspace_groups.c.group_id.desc()
        ).limit(limit + 1)
        rows = (await self._connection.execute(statement)).all()
        groups = tuple(_group_from_row(row) for row in rows)
        if len(groups) <= limit:
            return OrganizationSlice(groups, None)
        visible = groups[:limit]
        last = visible[-1]
        return OrganizationSlice(
            visible, OrganizationCursor(last.updated_at, last.group_id)
        )

    async def add_project(self, project: Project) -> None:
        try:
            await self._connection.execute(
                insert(projects).values(
                    project_id=project.project_id,
                    tenant_id=project.tenant_id,
                    group_id=project.group_id,
                    name=project.name,
                    normalized_name=project.normalized_name,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    latest_activity_at=project.latest_activity_at,
                    archived_at=project.archived_at,
                )
            )
        except IntegrityError as error:
            _translate_integrity(error)

    async def get_project(
        self, project_id: UUID, *, for_update: bool = False
    ) -> Project | None:
        statement = select(projects).where(projects.c.project_id == project_id)
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).first()
        return _project_from_row(row) if row is not None else None

    async def save_project(self, project: Project) -> None:
        try:
            await self._connection.execute(
                update(projects)
                .where(projects.c.project_id == project.project_id)
                .values(
                    name=project.name,
                    normalized_name=project.normalized_name,
                    updated_at=project.updated_at,
                    archived_at=project.archived_at,
                )
            )
        except IntegrityError as error:
            _translate_integrity(error)

    async def list_projects(
        self,
        *,
        group_id: UUID,
        include_archived: bool,
        limit: int,
        after: OrganizationCursor | None,
    ) -> OrganizationSlice[Project]:
        statement = select(projects).where(projects.c.group_id == group_id)
        if not include_archived:
            statement = statement.where(projects.c.archived_at.is_(None))
        if after is not None:
            statement = statement.where(
                tuple_(projects.c.latest_activity_at, projects.c.project_id)
                < tuple_(after.sort_at, after.resource_id)
            )
        statement = statement.order_by(
            projects.c.latest_activity_at.desc(), projects.c.project_id.desc()
        ).limit(limit + 1)
        rows = (await self._connection.execute(statement)).all()
        project_values = tuple(_project_from_row(row) for row in rows)
        if len(project_values) <= limit:
            return OrganizationSlice(project_values, None)
        visible = project_values[:limit]
        last = visible[-1]
        return OrganizationSlice(
            visible,
            OrganizationCursor(last.latest_activity_at, last.project_id),
        )

    async def record_project_activity(
        self, project_id: UUID, *, occurred_at: datetime
    ) -> None:
        await self._connection.execute(
            update(projects)
            .where(projects.c.project_id == project_id)
            .where(projects.c.latest_activity_at < occurred_at)
            .values(latest_activity_at=occurred_at)
        )


class PostgresOrganizationUnitOfWork:
    def __init__(self, connection: AsyncConnection) -> None:
        self.organization = PostgresOrganizationRepository(connection)
        self.should_commit = False

    async def commit(self) -> None:
        self.should_commit = True


class PostgresOrganizationUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def __call__(
        self,
        tenant_id: UUID,
        trace_id: UUID,
        span_id: UUID,
    ) -> AsyncIterator[PostgresOrganizationUnitOfWork]:
        del trace_id, span_id
        async with self._database.engine.connect() as connection:
            transaction = await connection.begin()
            await set_tenant_context(connection, tenant_id)
            unit_of_work = PostgresOrganizationUnitOfWork(connection)
            try:
                yield unit_of_work
            except Exception:
                await transaction.rollback()
                raise
            else:
                if unit_of_work.should_commit:
                    await transaction.commit()
                else:
                    await transaction.rollback()
