"""Event-type registry + envelope helpers (ENGINEERING.md §2.2, §2.3).

Every thing that happens is an event: a small JSON record with a fixed envelope
that every agent speaks. The constants here are the single source of truth for
event names so nothing is typo'd across agents.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# --- event types (registry, §2.3) ---
SPEC_RUN_REQUESTED = "spec.run.requested"
SPEC_INGESTED = "spec.ingested"
SCHEMA_PROPOSED = "schema.proposed"
SCHEMA_APPROVED = "schema.approved"
SCHEMA_REJECTED = "schema.rejected"
SCHEMA_CREATED = "schema.created"
CONTEXT_CHECKED = "context.checked"
CONTEXT_UPDATED = "context.updated"
INSIGHT_CREATED = "insight.created"
TOOL_CALLED = "tool.called"
CONTEXT_UPDATE_PROPOSED = "context.update.proposed"
RUN_ABORTED = "run.aborted"

# --- actors (§2.2) ---
ACTOR_INSTRUMENTATION = "instrumentation"
ACTOR_CONTEXT = "context"
ACTOR_ANALYTICS = "analytics"
ACTOR_MCP = "mcp"
ACTOR_USER = "user"
ACTOR_SYSTEM = "system"

EVENT_TYPES = {
    SPEC_RUN_REQUESTED,
    SPEC_INGESTED,
    SCHEMA_PROPOSED,
    SCHEMA_APPROVED,
    SCHEMA_REJECTED,
    SCHEMA_CREATED,
    CONTEXT_CHECKED,
    CONTEXT_UPDATED,
    INSIGHT_CREATED,
    TOOL_CALLED,
    CONTEXT_UPDATE_PROPOSED,
    RUN_ABORTED,
}


@dataclass
class Event:
    """The event envelope (§2.2) — the contract every agent speaks."""

    event_type: str
    aggregate_id: str
    actor: str
    payload: dict = field(default_factory=dict)
    trace_id: str = ""
    version: int = 0
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def as_row(self) -> dict:
        """Row shape for `atlys.event_log` (created_at is DateTime64(3) there).

        created_at is a naive-UTC datetime so clickhouse-connect can write it.
        """
        created = self.created_at
        if created.tzinfo is not None:
            created = created.astimezone(timezone.utc).replace(tzinfo=None)
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "version": self.version,
            "actor": self.actor,
            "payload": __import__("json").dumps(self.payload, default=str),
            "trace_id": self.trace_id,
            "created_at": created,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Event {self.event_type} agg={self.aggregate_id} v{self.version}>"


def new_event(
    event_type: str,
    aggregate_id: str,
    actor: str,
    payload: dict | None = None,
    trace_id: str = "",
    version: int = 0,
) -> Event:
    """Envelope helper — build an Event with sane defaults."""
    return Event(
        event_type=event_type,
        aggregate_id=aggregate_id,
        actor=actor,
        payload=payload or {},
        trace_id=trace_id,
        version=version,
    )
