from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zentra_adapter_clickhouse import AuditEntry, AuditRepository


def entry(**overrides: object) -> AuditEntry:
    values = {
        "trace_id": uuid4(),
        "span_id": uuid4(),
        "tenant_id": uuid4(),
        "investigation_id": uuid4(),
        "event_type": "Phase0SmokeTrace",
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
        "latency_ms": 1,
        "input_hash": "sha256:empty",
        "status": "success",
        "redacted_metadata": {"dependency": "clickhouse"},
    }
    values.update(overrides)
    return AuditEntry.model_validate(values)


def test_rejects_customer_data_in_metadata() -> None:
    with pytest.raises(ValidationError, match="raw_data"):
        entry(redacted_metadata={"nested": {"raw_data": [{"email": "secret"}]}})


def test_requires_artifact_scheme() -> None:
    with pytest.raises(ValidationError, match="artifact://"):
        entry(artifact_refs=("s3://customer-data",))


@pytest.mark.asyncio
async def test_repository_query_always_scopes_tenant_and_investigation() -> None:
    entry_id = uuid4()

    class Result:
        column_names = ["entry_id", "event_type"]
        result_rows = [
            (entry_id, "Phase0SmokeTrace"),
            (entry_id, "Phase0SmokeTrace"),
        ]

    class Client:
        query_text = ""
        parameters = {}

        def query(self, query: str, *, parameters: dict[str, object]) -> Result:
            self.query_text = query
            self.parameters = parameters
            return Result()

    client = Client()
    repository = AuditRepository(client)  # type: ignore[arg-type]
    tenant_id = uuid4()
    investigation_id = uuid4()

    rows = await repository.list_for_investigation(
        tenant_id=tenant_id,
        investigation_id=investigation_id,
    )

    assert "tenant_id = {tenant_id:UUID}" in client.query_text
    assert "investigation_id = {investigation_id:UUID}" in client.query_text
    assert client.parameters == {
        "tenant_id": str(tenant_id),
        "investigation_id": str(investigation_id),
    }
    assert rows == [{"entry_id": entry_id, "event_type": "Phase0SmokeTrace"}]
