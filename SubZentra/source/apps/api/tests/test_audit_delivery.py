from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from zentra_adapter_postgres import OutboxRecord

from zentra_api.audit_delivery import AuditDeliveryCoordinator


class Outbox:
    def __init__(self, record: OutboxRecord) -> None:
        self.record = record
        self.dispatched = False
        self.attempts = 0

    async def pending(self, **kwargs: object) -> tuple[OutboxRecord, ...]:
        return () if self.dispatched else (self.record,)

    async def mark_failed(self, *args: object) -> None:
        self.attempts += 1

    async def mark_dispatched(self, *args: object) -> None:
        self.dispatched = True


class UnitOfWork:
    def __init__(self, outbox: Outbox) -> None:
        self.outbox = outbox

    async def commit(self) -> None:
        return None


class Factory:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    @asynccontextmanager
    async def __call__(self, *args: object):
        yield self.unit_of_work


class FlakyAudit:
    def __init__(self) -> None:
        self.fail = True
        self.entries = []

    async def append(self, entry: object) -> None:
        if self.fail:
            raise RuntimeError("unavailable")
        self.entries.append(entry)


@pytest.mark.asyncio
async def test_outbox_delivery_retries_with_the_same_event_id() -> None:
    now = datetime.now(UTC)
    record = OutboxRecord(
        event_id=uuid4(),
        tenant_id=uuid4(),
        investigation_id=uuid4(),
        payload={
            "trace_id": str(uuid4()),
            "span_id": str(uuid4()),
            "event_type": "investigation.created",
            "status": "pending",
            "occurred_at": now.isoformat(),
            "input_hash": "sha256:fixture",
            "artifact_refs": [],
            "metadata": {"scenario_key": "eu_refund_spike"},
        },
        attempts=0,
        created_at=now,
        dispatched_at=None,
    )
    outbox = Outbox(record)
    audit = FlakyAudit()
    coordinator = AuditDeliveryCoordinator(
        unit_of_work_factory=Factory(UnitOfWork(outbox)),  # type: ignore[arg-type]
        audit=audit,  # type: ignore[arg-type]
    )

    assert (
        await coordinator.flush(
            tenant_id=record.tenant_id,
            investigation_id=record.investigation_id,
        )
        is False
    )
    assert outbox.attempts == 1

    audit.fail = False
    assert (
        await coordinator.flush(
            tenant_id=record.tenant_id,
            investigation_id=record.investigation_id,
        )
        is True
    )
    assert outbox.dispatched is True
    assert audit.entries[0].entry_id == record.event_id


def test_a_delivered_event_keeps_its_failed_rungs() -> None:
    """Reading only the ledger's columns dropped them, so degradation vanished
    from Replay the moment an event reached ClickHouse — the timeline showed
    less the longer you waited."""
    import json as json_module

    from zentra_api.audit_delivery import _metadata

    delivered = {
        "fallbacks": ["gemini/gemini-3.6-flash: circuit open"],
        "failed_publication_conditions": ["confident", "evidenced"],
        "agent_id": "insight_v1",
    }

    # ClickHouse hands the column back as a JSON string.
    parsed = _metadata(json_module.dumps(delivered))

    assert parsed["fallbacks"] == ["gemini/gemini-3.6-flash: circuit open"]
    assert parsed["failed_publication_conditions"] == ["confident", "evidenced"]


def test_metadata_reads_both_shapes_the_same_way() -> None:
    """The outbox hands back a dict and the ledger a string. A timeline that
    showed a field before delivery and lost it afterwards is worse than one
    that never showed it."""
    from zentra_api.audit_delivery import _metadata

    assert _metadata({"model": "claude-opus-5"}) == {"model": "claude-opus-5"}
    assert _metadata('{"model": "claude-opus-5"}') == {"model": "claude-opus-5"}
    # Anything else is absent metadata, not a crash mid-Replay.
    assert _metadata(None) == {}
    assert _metadata("not json") == {}
    assert _metadata("[]") == {}


def test_the_delivered_entry_keeps_the_outbox_ordering_floor() -> None:
    """The defect my first test missed.

    The floor is written to `audit_outbox.created_at`, and Replay sorts
    delivered rows on the ledger's `created_at`. Building the entry from the
    payload's `occurred_at` threw the floor away the moment an event was
    delivered — and a test that only read the outbox passed while that
    survived.
    """
    from datetime import UTC, datetime
    from uuid import UUID as _UUID

    from zentra_adapter_postgres import OutboxRecord

    from zentra_api.audit_delivery import AuditDeliveryCoordinator

    collided = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
    floored = datetime(2026, 7, 31, 12, 0, 0, 1, tzinfo=UTC)

    record = OutboxRecord(
        event_id=_UUID("50000000-0000-0000-0000-000000000005"),
        tenant_id=_UUID("20000000-0000-0000-0000-000000000002"),
        investigation_id=_UUID("30000000-0000-0000-0000-000000000003"),
        payload={
            "trace_id": str(_UUID(int=0)),
            "span_id": str(_UUID(int=0)),
            "event_type": "human_approval.granted",
            "status": "completed",
            # The un-floored instant two requests both claimed.
            "occurred_at": collided.isoformat(),
            "input_hash": "sha256:abc",
            "artifact_refs": [],
            "metadata": {},
        },
        # What the outbox actually stamped, after the floor.
        created_at=floored,
        dispatched_at=None,
        attempts=0,
    )

    entry = AuditDeliveryCoordinator._entry(record)

    assert entry.created_at == floored
    assert entry.created_at != collided


@pytest.mark.asyncio
async def test_an_event_in_both_sources_appears_once() -> None:
    """At-least-once delivery means the same event can be in the ledger and
    still undispatched in the outbox. A timeline that showed it twice would
    tell a reader a step happened twice."""
    from datetime import UTC, datetime
    from uuid import UUID as _UUID

    from zentra_adapter_postgres import OutboxRecord

    from zentra_api.audit_delivery import AuditDeliveryCoordinator

    tenant = _UUID("20000000-0000-0000-0000-000000000002")
    investigation = _UUID("30000000-0000-0000-0000-000000000003")
    shared = _UUID("50000000-0000-0000-0000-000000000005")
    moment = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)

    class Ledger:
        async def list_for_investigation(self, **_: object):
            return [
                {
                    "entry_id": str(shared),
                    "event_type": "investigation.completed",
                    "status": "completed",
                    "created_at": moment,
                    "artifact_refs": [],
                    "agent_id": "",
                    "step": None,
                    "model": "",
                    "redacted_metadata": "{}",
                }
            ]

    class Outbox:
        async def all_for_investigation(self, _investigation_id):
            # The same event, not yet marked dispatched.
            return [
                OutboxRecord(
                    event_id=shared,
                    tenant_id=tenant,
                    investigation_id=investigation,
                    payload={
                        "event_type": "investigation.completed",
                        "status": "completed",
                        "artifact_refs": [],
                        "metadata": {},
                    },
                    attempts=0,
                    created_at=moment,
                    dispatched_at=None,
                )
            ]

    class UnitOfWork:
        outbox = Outbox()

        async def commit(self) -> None:
            return None

    class Factory:
        def __call__(self, *_: object):
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def scope():
                yield UnitOfWork()

            return scope()

    coordinator = AuditDeliveryCoordinator(
        unit_of_work_factory=Factory(),  # type: ignore[arg-type]
        audit=Ledger(),  # type: ignore[arg-type]
    )

    timeline = await coordinator.list_timeline(
        tenant_id=tenant,
        investigation_id=investigation,
    )

    assert len(timeline) == 1
    # The delivered one wins: it is the authoritative record.
    assert timeline[0].delivery.value == "complete"
