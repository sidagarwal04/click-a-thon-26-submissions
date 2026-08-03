from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from zentra_adapter_clickhouse import AuditEntry, AuditRepository
from zentra_adapter_postgres import (
    OutboxRecord,
    PostgresInvestigationUnitOfWorkFactory,
)
from zentra_application_investigation import (
    AuditDelivery,
    TimelineEntry,
)


def _metadata(value: object) -> dict:
    """ClickHouse hands back a JSON string; the outbox hands back a dict.

    One reader for both, because a timeline that showed a field before
    delivery and lost it afterwards is worse than one that never showed it.
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return value if isinstance(value, dict) else {}


SYSTEM_TRACE_ID = UUID(int=0)
SYSTEM_SPAN_ID = UUID(int=0)


#: Error types an operator is expected to see. Only these are named in the
#: ledger; anything else reports as `unexpected`.
#:
#: An allowlist rather than a split on the first colon. The graph formats errors
#: as `Type: message`, but that is a convention on the far side of a queue, not
#: a guarantee, and one message with a colon in the wrong place would write
#: whatever preceded it into an immutable table.
_KNOWN_ERROR_CATEGORIES = frozenset(
    {
        "AbsentEvidenceError",
        "ConflictError",
        "ErasureError",
        "MalformedAgentResponseError",
        "NoEnabledAgentError",
        "ScenarioUnavailableError",
        "UncitableClaimError",
        "UngroundedClaimError",
        "UnsupportedCausalClaimError",
    }
)


def error_categories(errors: tuple[str, ...]) -> tuple[str, ...]:
    """Reduce error strings to types before they reach the ledger.

    ADR 0006 makes the ledger metadata-only, and an error message is the one
    place Agent prose can still get in: a refusal names the claim it refused and
    the figure it could not ground. ClickHouse is immutable and outside the
    erasure boundary, so a value that lands here outlives the deletion that was
    meant to erase it.

    The type is kept because Replay has to stay diagnosable — an operator must
    be able to tell a grounding refusal from a provider outage, and a ledger
    that recorded no reason at all would trade one failure for another.
    """
    return tuple(
        category
        if (category := error.split(":", maxsplit=1)[0].strip())
        in _KNOWN_ERROR_CATEGORIES
        else "unexpected"
        for error in errors
    )


class AuditDeliveryCoordinator:
    """Moves tenant-scoped outbox events into the immutable audit ledger."""

    def __init__(
        self,
        *,
        unit_of_work_factory: PostgresInvestigationUnitOfWorkFactory,
        audit: AuditRepository,
        retry_interval_seconds: float = 1,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._audit = audit
        self._retry_interval_seconds = retry_interval_seconds
        self._active_tenants: set[UUID] = set()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def flush(self, *, tenant_id: UUID, investigation_id: UUID) -> bool:
        self._active_tenants.add(tenant_id)
        async with self._unit_of_work_factory(
            tenant_id,
            SYSTEM_TRACE_ID,
            SYSTEM_SPAN_ID,
        ) as unit_of_work:
            pending = await unit_of_work.outbox.pending(
                investigation_id=investigation_id
            )

        delivered = True
        for record in pending:
            try:
                await self._audit.append(self._entry(record))
            except Exception:
                delivered = False
                async with self._unit_of_work_factory(
                    tenant_id,
                    SYSTEM_TRACE_ID,
                    SYSTEM_SPAN_ID,
                ) as unit_of_work:
                    await unit_of_work.outbox.mark_failed(
                        record.event_id,
                        "clickhouse_unavailable",
                    )
                    await unit_of_work.commit()
                continue
            async with self._unit_of_work_factory(
                tenant_id,
                SYSTEM_TRACE_ID,
                SYSTEM_SPAN_ID,
            ) as unit_of_work:
                await unit_of_work.outbox.mark_dispatched(
                    record.event_id,
                    datetime.now(UTC),
                )
                await unit_of_work.commit()
        return delivered

    async def list_timeline(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
    ) -> Sequence[TimelineEntry]:
        self._active_tenants.add(tenant_id)
        try:
            delivered_rows = await self._audit.list_for_investigation(
                tenant_id=tenant_id,
                investigation_id=investigation_id,
            )
        except Exception:
            delivered_rows = []
        async with self._unit_of_work_factory(
            tenant_id,
            SYSTEM_TRACE_ID,
            SYSTEM_SPAN_ID,
        ) as unit_of_work:
            outbox_rows = await unit_of_work.outbox.all_for_investigation(
                investigation_id
            )

        entries: dict[UUID, TimelineEntry] = {}
        for row in delivered_rows:
            entry_id = UUID(str(row["entry_id"]))
            # The ledger's own columns for identity, and its redacted metadata
            # for the rest. Reading only the columns dropped a delivered
            # event's failed rungs, so degradation vanished from Replay the
            # moment it reached ClickHouse.
            metadata = _metadata(row.get("redacted_metadata"))
            entries[entry_id] = TimelineEntry(
                entry_id=entry_id,
                event_type=str(row["event_type"]),
                status=str(row["status"]),
                created_at=row["created_at"],
                artifact_refs=tuple(row.get("artifact_refs", ())),
                delivery=AuditDelivery.COMPLETE,
                agent_id=row.get("agent_id") or None,
                step=row.get("step"),
                model=row.get("model") or None,
                fallbacks=tuple(metadata.get("fallbacks") or ()),
                failed_conditions=tuple(
                    metadata.get("failed_publication_conditions") or ()
                ),
                latency_ms=row.get("latency_ms"),
                total_cost_usd=(
                    str(row["total_cost_usd"])
                    if row.get("total_cost_usd") is not None
                    else None
                ),
                input_tokens=row.get("input_tokens"),
                output_tokens=row.get("output_tokens"),
            )
        for record in outbox_rows:
            if record.dispatched_at is not None:
                continue
            payload = record.payload
            metadata = _metadata(payload.get("metadata"))
            entries.setdefault(
                record.event_id,
                TimelineEntry(
                    entry_id=record.event_id,
                    event_type=str(payload["event_type"]),
                    status=str(payload["status"]),
                    created_at=record.created_at,
                    artifact_refs=tuple(payload.get("artifact_refs", ())),
                    delivery=AuditDelivery.PENDING,
                    agent_id=metadata.get("agent_id"),
                    step=metadata.get("step"),
                    model=metadata.get("model"),
                    fallbacks=tuple(metadata.get("fallbacks") or ()),
                    failed_conditions=tuple(
                        metadata.get("failed_publication_conditions") or ()
                    ),
                    latency_ms=metadata.get("latency_ms"),
                    total_cost_usd=metadata.get("total_cost_usd"),
                    input_tokens=metadata.get("input_tokens"),
                    output_tokens=metadata.get("output_tokens"),
                ),
            )
        return tuple(
            sorted(
                entries.values(),
                key=lambda entry: (entry.created_at, entry.entry_id),
            )
        )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._retry_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _retry_loop(self) -> None:
        while not self._stop.is_set():
            tenant_ids = set(self._active_tenants)
            with suppress(Exception):
                tenant_ids.update(await self._unit_of_work_factory.bound_tenant_ids())
            for tenant_id in tenant_ids:
                try:
                    async with self._unit_of_work_factory(
                        tenant_id,
                        SYSTEM_TRACE_ID,
                        SYSTEM_SPAN_ID,
                    ) as unit_of_work:
                        pending = await unit_of_work.outbox.pending()
                    investigation_ids = {record.investigation_id for record in pending}
                    for investigation_id in investigation_ids:
                        await self.flush(
                            tenant_id=tenant_id,
                            investigation_id=investigation_id,
                        )
                except Exception:
                    continue
            await asyncio.sleep(self._retry_interval_seconds)

    @staticmethod
    def _entry(record: OutboxRecord) -> AuditEntry:
        payload: dict[str, Any] = record.payload
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        metadata: dict[str, Any] = payload.get("metadata", {}) or {}
        latency_ms = int(metadata.get("latency_ms") or 0)
        return AuditEntry(
            entry_id=record.event_id,
            trace_id=UUID(str(payload["trace_id"])),
            span_id=UUID(str(payload["span_id"])),
            tenant_id=record.tenant_id,
            investigation_id=record.investigation_id,
            event_type=str(payload["event_type"]),
            agent_id=metadata.get("agent_id"),
            execution_id=(
                UUID(str(metadata["execution_id"]))
                if metadata.get("execution_id")
                else None
            ),
            step=metadata.get("step"),
            started_at=occurred_at - timedelta(milliseconds=latency_ms),
            completed_at=occurred_at,
            latency_ms=latency_ms,
            input_tokens=int(metadata.get("input_tokens") or 0),
            output_tokens=int(metadata.get("output_tokens") or 0),
            total_cost_usd=Decimal(str(metadata.get("total_cost_usd") or "0")),
            input_hash=str(payload["input_hash"]),
            outcome_kind=metadata.get("outcome_kind"),
            confidence=metadata.get("confidence"),
            model=metadata.get("model"),
            errors=error_categories(tuple(metadata.get("errors", ()))),
            status=str(payload["status"]),
            artifact_refs=tuple(payload.get("artifact_refs", ())),
            redacted_metadata=metadata,
            # `record.created_at`, not the payload's `occurred_at`. The
            # outbox is where each Investigation's timeline is made
            # strictly increasing; delivering the un-floored instant
            # would throw that away the moment an event reached the
            # ledger, and Replay sorts on this column.
            created_at=record.created_at,
        )
