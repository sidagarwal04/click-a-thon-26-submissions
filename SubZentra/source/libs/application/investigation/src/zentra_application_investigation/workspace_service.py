from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from zentra_domain_investigation import Group, Project

from .dto import AuthenticatedActor, PermissionDeniedError, Role
from .workspace_dto import (
    GroupDetail,
    OrganizationConflictError,
    OrganizationCursor,
    OrganizationNotFoundError,
    OrganizationPage,
    ProjectDetail,
)
from .workspace_ports import OrganizationUnitOfWorkFactory

MANAGER_ROLES = frozenset({Role.OWNER, Role.ADMIN})
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class OrganizationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: OrganizationUnitOfWorkFactory,
        now: Callable[[], datetime],
        new_id: Callable[[], UUID],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._now = now
        self._new_id = new_id

    async def create_group(
        self, actor: AuthenticatedActor, *, name: str
    ) -> GroupDetail:
        self._require_manager(actor)
        group = Group.create(
            group_id=self._new_id(),
            tenant_id=actor.tenant_id,
            name=name,
            now=self._now(),
        )
        async with self._uow(actor) as unit_of_work:
            await unit_of_work.organization.add_group(group)
            await unit_of_work.commit()
        return self._group_detail(group, actor)

    async def get_group(self, actor: AuthenticatedActor, group_id: UUID) -> GroupDetail:
        async with self._uow(actor) as unit_of_work:
            group = await unit_of_work.organization.get_group(group_id)
        return self._group_detail(self._require_group(group), actor)

    async def list_groups(
        self,
        actor: AuthenticatedActor,
        *,
        include_archived: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> OrganizationPage[GroupDetail]:
        limit = self._page_size(limit)
        after = OrganizationCursor.decode(cursor) if cursor is not None else None
        async with self._uow(actor) as unit_of_work:
            page = await unit_of_work.organization.list_groups(
                include_archived=include_archived, limit=limit, after=after
            )
        return OrganizationPage(
            items=tuple(self._group_detail(group, actor) for group in page.items),
            next_cursor=page.next_cursor.encode() if page.next_cursor else None,
        )

    async def rename_group(
        self, actor: AuthenticatedActor, group_id: UUID, *, name: str
    ) -> GroupDetail:
        return await self._change_group(
            actor, group_id, lambda group: group.rename(name, self._now())
        )

    async def archive_group(
        self, actor: AuthenticatedActor, group_id: UUID
    ) -> GroupDetail:
        return await self._change_group(
            actor, group_id, lambda group: group.archive(self._now())
        )

    async def restore_group(
        self, actor: AuthenticatedActor, group_id: UUID
    ) -> GroupDetail:
        return await self._change_group(
            actor, group_id, lambda group: group.restore(self._now())
        )

    async def create_project(
        self,
        actor: AuthenticatedActor,
        *,
        group_id: UUID,
        name: str,
    ) -> ProjectDetail:
        self._require_manager(actor)
        async with self._uow(actor) as unit_of_work:
            group = self._require_group(
                await unit_of_work.organization.get_group(group_id, for_update=True)
            )
            if group.archived_at is not None:
                raise OrganizationConflictError(
                    "Archived Groups cannot accept Projects"
                )
            project = Project.create(
                project_id=self._new_id(),
                tenant_id=actor.tenant_id,
                group_id=group_id,
                name=name,
                now=self._now(),
            )
            await unit_of_work.organization.add_project(project)
            await unit_of_work.commit()
        return self._project_detail(project, actor, group_archived=False)

    async def get_project(
        self, actor: AuthenticatedActor, project_id: UUID
    ) -> ProjectDetail:
        async with self._uow(actor) as unit_of_work:
            project = self._require_project(
                await unit_of_work.organization.get_project(project_id)
            )
            group = self._require_group(
                await unit_of_work.organization.get_group(project.group_id)
            )
        return self._project_detail(
            project, actor, group_archived=group.archived_at is not None
        )

    async def list_projects(
        self,
        actor: AuthenticatedActor,
        *,
        group_id: UUID,
        include_archived: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> OrganizationPage[ProjectDetail]:
        limit = self._page_size(limit)
        after = OrganizationCursor.decode(cursor) if cursor is not None else None
        async with self._uow(actor) as unit_of_work:
            group = self._require_group(
                await unit_of_work.organization.get_group(group_id)
            )
            page = await unit_of_work.organization.list_projects(
                group_id=group_id,
                include_archived=include_archived,
                limit=limit,
                after=after,
            )
        return OrganizationPage(
            items=tuple(
                self._project_detail(
                    project, actor, group_archived=group.archived_at is not None
                )
                for project in page.items
            ),
            next_cursor=page.next_cursor.encode() if page.next_cursor else None,
        )

    async def rename_project(
        self, actor: AuthenticatedActor, project_id: UUID, *, name: str
    ) -> ProjectDetail:
        return await self._change_project(
            actor, project_id, lambda project: project.rename(name, self._now())
        )

    async def archive_project(
        self, actor: AuthenticatedActor, project_id: UUID
    ) -> ProjectDetail:
        return await self._change_project(
            actor, project_id, lambda project: project.archive(self._now())
        )

    async def restore_project(
        self, actor: AuthenticatedActor, project_id: UUID
    ) -> ProjectDetail:
        return await self._change_project(
            actor, project_id, lambda project: project.restore(self._now())
        )

    async def _change_group(
        self,
        actor: AuthenticatedActor,
        group_id: UUID,
        change: Callable[[Group], None],
    ) -> GroupDetail:
        self._require_manager(actor)
        async with self._uow(actor) as unit_of_work:
            group = self._require_group(
                await unit_of_work.organization.get_group(group_id, for_update=True)
            )
            change(group)
            await unit_of_work.organization.save_group(group)
            await unit_of_work.commit()
        return self._group_detail(group, actor)

    async def _change_project(
        self,
        actor: AuthenticatedActor,
        project_id: UUID,
        change: Callable[[Project], None],
    ) -> ProjectDetail:
        self._require_manager(actor)
        async with self._uow(actor) as unit_of_work:
            project = self._require_project(
                await unit_of_work.organization.get_project(project_id, for_update=True)
            )
            group = self._require_group(
                await unit_of_work.organization.get_group(project.group_id)
            )
            if group.archived_at is not None:
                raise OrganizationConflictError(
                    "Archived Groups make Projects read-only"
                )
            change(project)
            await unit_of_work.organization.save_project(project)
            await unit_of_work.commit()
        return self._project_detail(project, actor, group_archived=False)

    def _uow(self, actor: AuthenticatedActor):
        return self._unit_of_work_factory(
            actor.tenant_id, actor.trace_id, actor.span_id
        )

    @staticmethod
    def _require_manager(actor: AuthenticatedActor) -> None:
        if actor.role not in MANAGER_ROLES:
            raise PermissionDeniedError("This membership cannot organize workspaces")

    @staticmethod
    def _require_group(group: Group | None) -> Group:
        if group is None:
            raise OrganizationNotFoundError("Group was not found")
        return group

    @staticmethod
    def _require_project(project: Project | None) -> Project:
        if project is None:
            raise OrganizationNotFoundError("Project was not found")
        return project

    @staticmethod
    def _page_size(limit: int) -> int:
        if limit < 1 or limit > MAX_PAGE_SIZE:
            raise ValueError(f"Page size must be between 1 and {MAX_PAGE_SIZE}")
        return limit

    @staticmethod
    def _group_detail(group: Group, actor: AuthenticatedActor) -> GroupDetail:
        return GroupDetail(
            group_id=group.group_id,
            name=group.name,
            created_at=group.created_at,
            updated_at=group.updated_at,
            archived_at=group.archived_at,
            can_manage=actor.role in MANAGER_ROLES,
        )

    @staticmethod
    def _project_detail(
        project: Project,
        actor: AuthenticatedActor,
        *,
        group_archived: bool,
    ) -> ProjectDetail:
        return ProjectDetail(
            project_id=project.project_id,
            group_id=project.group_id,
            name=project.name,
            created_at=project.created_at,
            updated_at=project.updated_at,
            latest_activity_at=project.latest_activity_at,
            archived_at=project.archived_at,
            can_manage=actor.role in MANAGER_ROLES and not group_archived,
        )
