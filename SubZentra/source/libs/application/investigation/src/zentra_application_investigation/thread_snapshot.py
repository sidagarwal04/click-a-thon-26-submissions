from __future__ import annotations

from uuid import UUID

from zentra_domain_investigation import (
    TERMINAL_STATUSES,
    Investigation,
    InvestigationStatus,
    InvestigationThread,
    Project,
    ThreadMessage,
    ThreadStatus,
)

from .dto import AuthenticatedActor, Role, UsageSummary
from .thread_dto import (
    RoutingResult,
    ThreadDetail,
    ThreadInvestigationSummary,
    ThreadMessageDetail,
    ThreadNotFoundError,
)

THREAD_MUTATOR_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.MEMBER})
EMPTY_USAGE = UsageSummary()


def require_project(project: Project | None) -> Project:
    if project is None:
        raise ThreadNotFoundError("Project was not found")
    return project


def validate_page_size(limit: int, maximum: int) -> int:
    if limit < 1 or limit > maximum:
        raise ValueError(f"Page size must be between 1 and {maximum}")
    return limit


def build_thread_detail(
    thread: InvestigationThread,
    messages: tuple[ThreadMessage, ...],
    investigation_id: UUID | None,
    routing: RoutingResult | None,
    actor: AuthenticatedActor,
    *,
    investigations: tuple[Investigation, ...] = (),
    investigation_summaries: tuple[ThreadInvestigationSummary, ...] = (),
    event_cursor: int = 0,
    usage: UsageSummary = EMPTY_USAGE,
) -> ThreadDetail:
    can_mutate = actor.role in THREAD_MUTATOR_ROLES
    is_archived = thread.status is ThreadStatus.ARCHIVED
    latest = investigations[-1] if investigations else None
    latest_terminal = latest is not None and latest.status in TERMINAL_STATUSES
    return ThreadDetail(
        thread_id=thread.thread_id,
        project_id=thread.project_id,
        title=thread.title,
        status=thread.status,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        latest_activity_at=thread.latest_activity_at,
        messages=tuple(
            ThreadMessageDetail(
                message_id=message.message_id,
                kind=message.kind,
                content=message.content,
                created_at=message.created_at,
                authored_by_user=message.author_id is not None,
            )
            for message in messages
        ),
        investigation_id=investigation_id,
        routing=routing,
        can_append_message=(
            can_mutate
            and (
                thread.status is ThreadStatus.DRAFT
                or (thread.status is ThreadStatus.ACTIVE and latest_terminal)
            )
        ),
        can_archive=can_mutate and not is_archived,
        can_restore=can_mutate and is_archived,
        can_delete=(
            can_mutate
            and thread.status is ThreadStatus.DRAFT
            and investigation_id is None
        ),
        investigations=investigation_summaries
        or tuple(
            ThreadInvestigationSummary(
                investigation_id=value.investigation_id,
                sequence=value.thread_sequence or 0,
                status=value.status,
                parent_investigation_id=value.parent_investigation_id,
                retry_of_investigation_id=value.retry_of_investigation_id,
                created_at=value.created_at,
                updated_at=value.updated_at,
            )
            for value in investigations
        ),
        event_cursor=event_cursor,
        can_cancel=(can_mutate and latest is not None and not latest_terminal),
        can_retry=(
            can_mutate
            and latest is not None
            and latest.status
            in {InvestigationStatus.FAILED, InvestigationStatus.CANCELLED}
        ),
        usage=usage,
    )
