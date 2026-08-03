from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from zentra_application_investigation import (
    OrganizationConflictError,
    OrganizationCursorError,
    OrganizationNotFoundError,
    PermissionDeniedError,
)
from zentra_domain_investigation import OrganizationNameError

from .request_context import RequestContext, authenticated_context
from .workspace_schemas import (
    GroupPageResponse,
    GroupResponse,
    OrganizationNameRequest,
    ProjectPageResponse,
    ProjectResponse,
)

router = APIRouter(prefix="/v1")
AuthenticatedRequest = Annotated[RequestContext, Depends(authenticated_context)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _workspace_error(error: Exception) -> NoReturn:
    if isinstance(error, PermissionDeniedError):
        code, status_code = "permission_denied", status.HTTP_403_FORBIDDEN
    elif isinstance(error, OrganizationNotFoundError):
        code, status_code = "workspace_not_found", status.HTTP_404_NOT_FOUND
    elif isinstance(error, OrganizationConflictError):
        code, status_code = "workspace_conflict", status.HTTP_409_CONFLICT
    elif isinstance(
        error, (OrganizationCursorError, OrganizationNameError, ValueError)
    ):
        code, status_code = "invalid_workspace", status.HTTP_422_UNPROCESSABLE_ENTITY
    else:  # pragma: no cover
        raise error
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(error)},
    ) from error


@router.post(
    "/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED
)
async def create_group(
    body: OrganizationNameRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> GroupResponse:
    try:
        detail = await request.app.state.dependencies.organization.create_group(
            resolved.actor, name=body.name
        )
    except (
        PermissionDeniedError,
        OrganizationConflictError,
        OrganizationNameError,
    ) as error:
        _workspace_error(error)
    return GroupResponse.from_detail(detail)


@router.get("/groups", response_model=GroupPageResponse)
async def list_groups(
    request: Request,
    resolved: AuthenticatedRequest,
    limit: PageSize = 50,
    cursor: str | None = None,
    include_archived: bool = False,
) -> GroupPageResponse:
    try:
        page = await request.app.state.dependencies.organization.list_groups(
            resolved.actor,
            limit=limit,
            cursor=cursor,
            include_archived=include_archived,
        )
    except (OrganizationCursorError, ValueError) as error:
        _workspace_error(error)
    return GroupPageResponse(
        items=[GroupResponse.from_detail(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> GroupResponse:
    try:
        detail = await request.app.state.dependencies.organization.get_group(
            resolved.actor, group_id
        )
    except OrganizationNotFoundError as error:
        _workspace_error(error)
    return GroupResponse.from_detail(detail)


@router.patch("/groups/{group_id}", response_model=GroupResponse)
async def rename_group(
    group_id: UUID,
    body: OrganizationNameRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> GroupResponse:
    try:
        detail = await request.app.state.dependencies.organization.rename_group(
            resolved.actor, group_id, name=body.name
        )
    except (
        PermissionDeniedError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationNameError,
    ) as error:
        _workspace_error(error)
    return GroupResponse.from_detail(detail)


@router.post("/groups/{group_id}/archive", response_model=GroupResponse)
async def archive_group(
    group_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> GroupResponse:
    try:
        detail = await request.app.state.dependencies.organization.archive_group(
            resolved.actor, group_id
        )
    except (PermissionDeniedError, OrganizationNotFoundError) as error:
        _workspace_error(error)
    return GroupResponse.from_detail(detail)


@router.post("/groups/{group_id}/restore", response_model=GroupResponse)
async def restore_group(
    group_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> GroupResponse:
    try:
        detail = await request.app.state.dependencies.organization.restore_group(
            resolved.actor, group_id
        )
    except (PermissionDeniedError, OrganizationNotFoundError) as error:
        _workspace_error(error)
    return GroupResponse.from_detail(detail)


@router.post(
    "/groups/{group_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    group_id: UUID,
    body: OrganizationNameRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> ProjectResponse:
    try:
        detail = await request.app.state.dependencies.organization.create_project(
            resolved.actor, group_id=group_id, name=body.name
        )
    except (
        PermissionDeniedError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationNameError,
    ) as error:
        _workspace_error(error)
    return ProjectResponse.from_detail(detail)


@router.get("/groups/{group_id}/projects", response_model=ProjectPageResponse)
async def list_projects(
    group_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
    limit: PageSize = 50,
    cursor: str | None = None,
    include_archived: bool = False,
) -> ProjectPageResponse:
    try:
        page = await request.app.state.dependencies.organization.list_projects(
            resolved.actor,
            group_id=group_id,
            limit=limit,
            cursor=cursor,
            include_archived=include_archived,
        )
    except (OrganizationNotFoundError, OrganizationCursorError, ValueError) as error:
        _workspace_error(error)
    return ProjectPageResponse(
        items=[ProjectResponse.from_detail(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ProjectResponse:
    try:
        detail = await request.app.state.dependencies.organization.get_project(
            resolved.actor, project_id
        )
    except OrganizationNotFoundError as error:
        _workspace_error(error)
    return ProjectResponse.from_detail(detail)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def rename_project(
    project_id: UUID,
    body: OrganizationNameRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> ProjectResponse:
    try:
        detail = await request.app.state.dependencies.organization.rename_project(
            resolved.actor, project_id, name=body.name
        )
    except (
        PermissionDeniedError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationNameError,
    ) as error:
        _workspace_error(error)
    return ProjectResponse.from_detail(detail)


@router.post("/projects/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ProjectResponse:
    try:
        detail = await request.app.state.dependencies.organization.archive_project(
            resolved.actor, project_id
        )
    except (
        PermissionDeniedError,
        OrganizationNotFoundError,
        OrganizationConflictError,
    ) as error:
        _workspace_error(error)
    return ProjectResponse.from_detail(detail)


@router.post("/projects/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(
    project_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ProjectResponse:
    try:
        detail = await request.app.state.dependencies.organization.restore_project(
            resolved.actor, project_id
        )
    except (
        PermissionDeniedError,
        OrganizationNotFoundError,
        OrganizationConflictError,
    ) as error:
        _workspace_error(error)
    return ProjectResponse.from_detail(detail)
