from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class OrganizationNotFoundError(LookupError):
    pass


class OrganizationConflictError(RuntimeError):
    pass


class OrganizationNameConflictError(OrganizationConflictError):
    pass


class OrganizationCursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OrganizationCursor:
    sort_at: datetime
    resource_id: UUID

    def encode(self) -> str:
        payload = json.dumps(
            {"sort_at": self.sort_at.isoformat(), "id": str(self.resource_id)},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode()

    @classmethod
    def decode(cls, value: str) -> OrganizationCursor:
        try:
            padded = value + "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            return cls(
                sort_at=datetime.fromisoformat(payload["sort_at"]),
                resource_id=UUID(payload["id"]),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise OrganizationCursorError("The workspace cursor is invalid") from error


@dataclass(frozen=True, slots=True)
class GroupDetail:
    group_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    can_manage: bool


@dataclass(frozen=True, slots=True)
class ProjectDetail:
    project_id: UUID
    group_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    latest_activity_at: datetime
    archived_at: datetime | None
    can_manage: bool


@dataclass(frozen=True, slots=True)
class OrganizationPage[T]:
    items: tuple[T, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class OrganizationSlice[T]:
    items: tuple[T, ...]
    next_cursor: OrganizationCursor | None
