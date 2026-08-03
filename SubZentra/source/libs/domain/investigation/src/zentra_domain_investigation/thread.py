from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

MAX_THREAD_MESSAGE_LENGTH = 4_000
MAX_THREAD_TITLE_LENGTH = 80


class ThreadStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ThreadMessageKind(StrEnum):
    USER_QUESTION = "user_question"
    USER_CLARIFICATION = "user_clarification"
    ROUTER_CLARIFICATION = "router_clarification"
    SAFE_SYSTEM = "safe_system"


class ThreadMessageError(ValueError):
    pass


class ThreadTransitionError(RuntimeError):
    pass


def normalize_message_content(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ThreadMessageError("A Thread message cannot be empty")
    if len(normalized) > MAX_THREAD_MESSAGE_LENGTH:
        raise ThreadMessageError(
            f"A Thread message cannot exceed {MAX_THREAD_MESSAGE_LENGTH} characters"
        )
    if any(
        unicodedata.category(character).startswith("C")
        and character not in {"\n", "\t"}
        for character in normalized
    ):
        raise ThreadMessageError("A Thread message contains unsupported characters")
    return normalized


@dataclass(frozen=True, slots=True)
class ThreadMessage:
    message_id: UUID
    thread_id: UUID
    tenant_id: UUID
    author_id: UUID | None
    kind: ThreadMessageKind
    content: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        message_id: UUID,
        thread_id: UUID,
        tenant_id: UUID,
        author_id: UUID | None,
        kind: ThreadMessageKind,
        content: str,
        now: datetime,
    ) -> ThreadMessage:
        return cls(
            message_id=message_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            author_id=author_id,
            kind=kind,
            content=normalize_message_content(content),
            created_at=now,
        )


@dataclass(slots=True)
class InvestigationThread:
    thread_id: UUID
    tenant_id: UUID
    project_id: UUID
    initiating_message_id: UUID
    title: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime
    latest_activity_at: datetime
    archived_at: datetime | None = None
    archived_from_status: ThreadStatus | None = None

    @classmethod
    def create(
        cls,
        *,
        thread_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
        initiating_message_id: UUID,
        title: str,
        now: datetime,
    ) -> InvestigationThread:
        normalized_title = " ".join(title.split()).strip()
        if not normalized_title or len(normalized_title) > MAX_THREAD_TITLE_LENGTH:
            raise ThreadMessageError("A Thread title is invalid")
        return cls(
            thread_id=thread_id,
            tenant_id=tenant_id,
            project_id=project_id,
            initiating_message_id=initiating_message_id,
            title=normalized_title,
            status=ThreadStatus.DRAFT,
            created_at=now,
            updated_at=now,
            latest_activity_at=now,
        )

    def activate(self, now: datetime) -> None:
        self.ensure_writable()
        self.status = ThreadStatus.ACTIVE
        self.updated_at = now
        self.latest_activity_at = now

    def record_message(self, now: datetime) -> None:
        self.ensure_writable()
        self.updated_at = now
        self.latest_activity_at = now

    def ensure_writable(self) -> None:
        if self.status is ThreadStatus.ARCHIVED:
            raise ThreadTransitionError("Archived Threads cannot accept messages")

    def archive(self, now: datetime) -> None:
        if self.status is ThreadStatus.ARCHIVED:
            return
        self.archived_from_status = self.status
        self.status = ThreadStatus.ARCHIVED
        self.archived_at = now
        self.updated_at = now

    def restore(self, now: datetime) -> None:
        if self.status is not ThreadStatus.ARCHIVED:
            return
        self.status = self.archived_from_status or ThreadStatus.DRAFT
        self.archived_from_status = None
        self.archived_at = None
        self.updated_at = now

    def ensure_deletable(self, *, has_analytical_work: bool) -> None:
        if self.status is not ThreadStatus.DRAFT or has_analytical_work:
            raise ThreadTransitionError(
                "Threads with analytical work must be archived rather than deleted"
            )
