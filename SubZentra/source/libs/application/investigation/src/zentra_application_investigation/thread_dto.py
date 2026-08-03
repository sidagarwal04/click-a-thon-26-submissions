from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from zentra_domain_agent_execution import OutcomeSignal
from zentra_domain_investigation import (
    DraftFinding,
    EvidenceCitation,
    Finding,
    HumanApproval,
    InvestigationStatus,
    ThreadMessageKind,
    ThreadStatus,
)

from .dto import AuditDelivery, UsageSummary


class ThreadNotFoundError(LookupError):
    pass


class ThreadConflictError(RuntimeError):
    pass


class ThreadCursorError(ValueError):
    pass


class RoutingDisposition(StrEnum):
    RESOLVED = "resolved"
    # Read-compatibility only (ADR-0023). Routing matched free text against two
    # governed scenarios and refused everything else; a tenant's questions are
    # its own now, so nothing produces these. Threads and Work Feed events
    # written before that carry them and must stay readable.
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ThreadCursor:
    activity_at: datetime
    thread_id: UUID

    def encode(self) -> str:
        payload = json.dumps(
            {
                "activity_at": self.activity_at.isoformat(),
                "thread_id": str(self.thread_id),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode()

    @classmethod
    def decode(cls, value: str) -> ThreadCursor:
        try:
            padded = value + "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            activity_at = datetime.fromisoformat(payload["activity_at"])
            if activity_at.tzinfo is None or activity_at.utcoffset() is None:
                raise ValueError("Cursor timestamps must include a UTC offset")
            return cls(
                activity_at=activity_at.astimezone(UTC),
                thread_id=UUID(payload["thread_id"]),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ThreadCursorError("The Thread cursor is invalid") from error


@dataclass(frozen=True, slots=True)
class RoutingResult:
    disposition: RoutingDisposition
    scenario_key: str | None
    canonical_question: str | None
    clarification: str | None
    suggestions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThreadMessageDetail:
    message_id: UUID
    kind: ThreadMessageKind
    content: str
    created_at: datetime
    authored_by_user: bool


@dataclass(frozen=True, slots=True)
class ThreadSummary:
    thread_id: UUID
    project_id: UUID
    title: str
    status: ThreadStatus
    latest_activity_at: datetime
    investigation_id: UUID | None


@dataclass(frozen=True, slots=True)
class ThreadInvestigationSummary:
    investigation_id: UUID
    sequence: int
    status: InvestigationStatus
    parent_investigation_id: UUID | None
    retry_of_investigation_id: UUID | None
    created_at: datetime
    updated_at: datetime
    question: str = ""
    # See InvestigationDetail.scenario_key — read-compatibility only.
    scenario_key: str | None = None
    version: int = 0
    evaluation_attempts: int = 0
    finished_at: datetime | None = None
    finding: Finding | None = None
    draft_finding: DraftFinding | None = None
    outcome: OutcomeSignal | None = None
    approval: HumanApproval | None = None
    citations: tuple[EvidenceCitation, ...] = ()
    audit_delivery: AuditDelivery = AuditDelivery.COMPLETE
    usage: UsageSummary = UsageSummary()
    can_decide_approval: bool = False


@dataclass(frozen=True, slots=True)
class ThreadDetail:
    thread_id: UUID
    project_id: UUID
    title: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime
    latest_activity_at: datetime
    messages: tuple[ThreadMessageDetail, ...]
    investigation_id: UUID | None
    routing: RoutingResult | None
    can_append_message: bool
    can_archive: bool
    can_restore: bool
    can_delete: bool
    investigations: tuple[ThreadInvestigationSummary, ...] = ()
    event_cursor: int = 0
    can_cancel: bool = False
    can_retry: bool = False
    usage: UsageSummary = UsageSummary()


@dataclass(frozen=True, slots=True)
class ThreadPage:
    items: tuple[ThreadSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class ThreadSlice:
    items: tuple[ThreadSummary, ...]
    next_cursor: ThreadCursor | None
