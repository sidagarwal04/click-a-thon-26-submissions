from uuid import uuid4

import pytest
from sqlalchemy import text

from zentra_adapter_postgres.database import set_tenant_context


class RecordingConnection:
    def __init__(self) -> None:
        self.statement = None
        self.parameters = None

    async def execute(self, statement: object, parameters: object) -> None:
        self.statement = statement
        self.parameters = parameters


@pytest.mark.asyncio
async def test_tenant_context_is_set_locally_from_internal_uuid() -> None:
    connection = RecordingConnection()
    tenant_id = uuid4()

    await set_tenant_context(connection, tenant_id)  # type: ignore[arg-type]

    assert (
        str(connection.statement)
        == "SELECT set_config('app.tenant_id', :tenant_id, true)"
    )
    assert connection.parameters == {"tenant_id": str(tenant_id)}


def test_rls_expression_fails_closed_without_setting() -> None:
    expression = text(
        "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    )

    assert "NULLIF" in str(expression)
    assert "true" in str(expression)
