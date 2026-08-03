from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from zentra_domain_investigation import Group, Project

from .workspace_dto import OrganizationCursor, OrganizationSlice


class OrganizationRepository(Protocol):
    async def add_group(self, group: Group) -> None: ...

    async def get_group(
        self, group_id: UUID, *, for_update: bool = False
    ) -> Group | None: ...

    async def save_group(self, group: Group) -> None: ...

    async def list_groups(
        self,
        *,
        include_archived: bool,
        limit: int,
        after: OrganizationCursor | None,
    ) -> OrganizationSlice[Group]: ...

    async def add_project(self, project: Project) -> None: ...

    async def get_project(
        self, project_id: UUID, *, for_update: bool = False
    ) -> Project | None: ...

    async def save_project(self, project: Project) -> None: ...

    async def list_projects(
        self,
        *,
        group_id: UUID,
        include_archived: bool,
        limit: int,
        after: OrganizationCursor | None,
    ) -> OrganizationSlice[Project]: ...

    async def record_project_activity(
        self, project_id: UUID, *, occurred_at: datetime
    ) -> None: ...


class OrganizationUnitOfWork(Protocol):
    organization: OrganizationRepository

    async def commit(self) -> None: ...


class OrganizationUnitOfWorkFactory(Protocol):
    def __call__(
        self, tenant_id: UUID, trace_id: UUID, span_id: UUID
    ) -> AbstractAsyncContextManager[OrganizationUnitOfWork]: ...
