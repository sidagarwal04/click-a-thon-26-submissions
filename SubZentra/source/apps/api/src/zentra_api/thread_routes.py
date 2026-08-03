from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from zentra_application_investigation import (
    PermissionDeniedError,
    ThreadConflictError,
    ThreadCursorError,
    ThreadNotFoundError,
)
from zentra_domain_investigation import ThreadMessageError, ThreadTransitionError

from .active_connection import (
    AmbiguousDataConnectionError,
    active_data_connection_id,
)
from .request_context import RequestContext, authenticated_context
from .thread_schemas import ThreadMessageRequest, ThreadPageResponse, ThreadResponse

router = APIRouter(prefix="/v1")
AuthenticatedRequest = Annotated[RequestContext, Depends(authenticated_context)]
PageSize = Annotated[int, Query(ge=1, le=100)]


async def _active_connection(dependencies: object, actor: object) -> UUID | None:
    """The Data Connection this Thread's Investigations query."""
    try:
        return await active_data_connection_id(
            dependencies.connector,  # type: ignore[attr-defined]
            actor,  # type: ignore[arg-type]
        )
    except AmbiguousDataConnectionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _thread_error(error: Exception) -> NoReturn:
    if isinstance(error, PermissionDeniedError):
        code, status_code = "permission_denied", status.HTTP_403_FORBIDDEN
    elif isinstance(error, ThreadNotFoundError):
        code, status_code = "thread_not_found", status.HTTP_404_NOT_FOUND
    elif isinstance(error, (ThreadConflictError, ThreadTransitionError)):
        code, status_code = "thread_conflict", status.HTTP_409_CONFLICT
    elif isinstance(error, (ThreadMessageError, ThreadCursorError, ValueError)):
        code, status_code = "invalid_thread", status.HTTP_422_UNPROCESSABLE_ENTITY
    else:  # pragma: no cover
        raise error
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(error)},
    ) from error


@router.post(
    "/projects/{project_id}/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    project_id: UUID,
    body: ThreadMessageRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> ThreadResponse:
    dependencies = request.app.state.dependencies
    try:
        detail = await dependencies.threads.create(
            resolved.actor,
            project_id=project_id,
            content=body.message,
            data_connection_id=await _active_connection(dependencies, resolved.actor),
        )
    except (
        PermissionDeniedError,
        ThreadNotFoundError,
        ThreadConflictError,
        ThreadMessageError,
    ) as error:
        _thread_error(error)
    return ThreadResponse.from_detail(detail)


@router.get("/projects/{project_id}/threads", response_model=ThreadPageResponse)
async def list_threads(
    project_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
    limit: PageSize = 50,
    cursor: str | None = None,
    include_archived: bool = False,
) -> ThreadPageResponse:
    try:
        detail = await request.app.state.dependencies.threads.list(
            resolved.actor,
            project_id=project_id,
            limit=limit,
            cursor=cursor,
            include_archived=include_archived,
        )
    except (ThreadNotFoundError, ThreadCursorError, ValueError) as error:
        _thread_error(error)
    return ThreadPageResponse.from_detail(detail)


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ThreadResponse:
    try:
        detail = await request.app.state.dependencies.threads.get(
            resolved.actor, thread_id
        )
    except ThreadNotFoundError as error:
        _thread_error(error)
    return ThreadResponse.from_detail(detail)


@router.get(
    "/threads/{thread_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_thread_events(
    thread_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
    after: int | None = Query(default=None, ge=0),
) -> StreamingResponse:
    header_cursor = request.headers.get("last-event-id")
    try:
        cursor = after if after is not None else int(header_cursor or "0")
        await request.app.state.dependencies.threads.event_cursor(
            resolved.actor, thread_id
        )
    except (ThreadNotFoundError, ValueError) as error:
        _thread_error(error)

    async def event_stream() -> AsyncIterator[str]:
        nonlocal cursor
        heartbeat_elapsed = 0
        while not await request.is_disconnected():
            events = await request.app.state.dependencies.threads.events(
                resolved.actor,
                thread_id=thread_id,
                after=cursor,
            )
            if events:
                for event in events:
                    cursor = event.sequence
                    yield (
                        f"id: {event.sequence}\n"
                        f"event: {event.kind.value}\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                heartbeat_elapsed = 0
            else:
                await asyncio.sleep(1)
                heartbeat_elapsed += 1
                if heartbeat_elapsed >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat_elapsed = 0

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/threads/{thread_id}/messages", response_model=ThreadResponse)
async def append_thread_message(
    thread_id: UUID,
    body: ThreadMessageRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> ThreadResponse:
    dependencies = request.app.state.dependencies
    try:
        detail = await dependencies.threads.append(
            resolved.actor,
            thread_id=thread_id,
            content=body.message,
            data_connection_id=await _active_connection(dependencies, resolved.actor),
        )
    except (
        PermissionDeniedError,
        ThreadNotFoundError,
        ThreadConflictError,
        ThreadMessageError,
    ) as error:
        _thread_error(error)
    return ThreadResponse.from_detail(detail)


@router.post("/threads/{thread_id}/archive", response_model=ThreadResponse)
async def archive_thread(
    thread_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ThreadResponse:
    try:
        detail = await request.app.state.dependencies.threads.archive(
            resolved.actor, thread_id
        )
    except (PermissionDeniedError, ThreadNotFoundError) as error:
        _thread_error(error)
    return ThreadResponse.from_detail(detail)


@router.post("/threads/{thread_id}/restore", response_model=ThreadResponse)
async def restore_thread(
    thread_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> ThreadResponse:
    try:
        detail = await request.app.state.dependencies.threads.restore(
            resolved.actor, thread_id
        )
    except (
        PermissionDeniedError,
        ThreadNotFoundError,
        ThreadConflictError,
    ) as error:
        _thread_error(error)
    return ThreadResponse.from_detail(detail)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID, request: Request, resolved: AuthenticatedRequest
) -> None:
    try:
        await request.app.state.dependencies.threads.delete(resolved.actor, thread_id)
    except (
        PermissionDeniedError,
        ThreadNotFoundError,
        ThreadConflictError,
    ) as error:
        _thread_error(error)
