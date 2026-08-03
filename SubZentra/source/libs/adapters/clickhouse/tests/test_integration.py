from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import DatabaseError

from zentra_adapter_clickhouse import AuditEntry, AuditRepository

CLICKHOUSE_HOST = os.getenv("TEST_CLICKHOUSE_HOST")

pytestmark = pytest.mark.skipif(
    not CLICKHOUSE_HOST,
    reason="local ClickHouse integration service is not configured",
)


@pytest.mark.asyncio
async def test_append_replay_order_and_restricted_grants() -> None:
    assert CLICKHOUSE_HOST is not None
    tenant_id = uuid4()
    investigation_id = uuid4()
    now = datetime.now(UTC)
    repository = AuditRepository.connect(
        host=CLICKHOUSE_HOST,
        port=int(os.getenv("TEST_CLICKHOUSE_PORT", "8123")),
        username="zentra_audit_app",
        password="zentra_audit_app",
        database="zentra_audit",
        secure=False,
    )

    later_entry = AuditEntry(
        entry_id=UUID("81000000-0000-0000-0000-000000000002"),
        trace_id=uuid4(),
        span_id=uuid4(),
        tenant_id=tenant_id,
        investigation_id=investigation_id,
        event_type="integration.replay",
        started_at=now + timedelta(seconds=1),
        completed_at=now + timedelta(seconds=1),
        latency_ms=0,
        input_hash="sha256:later",
        status="success",
        redacted_metadata={"fixture": True},
        created_at=now + timedelta(seconds=1),
    )
    earlier_entry = later_entry.model_copy(
        update={
            "entry_id": UUID("81000000-0000-0000-0000-000000000001"),
            "input_hash": "sha256:earlier",
            "started_at": now,
            "completed_at": now,
            "created_at": now,
        }
    )
    await repository.append(later_entry)
    await repository.append(earlier_entry)

    replay = await repository.list_for_investigation(
        tenant_id=tenant_id,
        investigation_id=investigation_id,
    )
    assert [row["input_hash"] for row in replay] == [
        "sha256:earlier",
        "sha256:later",
    ]
    await repository.close()

    runtime_client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=int(os.getenv("TEST_CLICKHOUSE_PORT", "8123")),
        username="zentra_audit_app",
        password="zentra_audit_app",
        database="zentra_audit",
    )
    with pytest.raises(DatabaseError, match="Not enough privileges"):
        runtime_client.command(
            "ALTER TABLE audit_entries UPDATE status = 'tampered' "
            f"WHERE tenant_id = '{tenant_id}'"
        )
    runtime_client.close()
