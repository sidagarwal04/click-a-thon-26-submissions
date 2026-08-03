from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_application_investigation import (
    AuthenticatedActor,
    OrganizationNameConflictError,
    OrganizationNotFoundError,
    OrganizationService,
    Role,
)

from zentra_adapter_postgres import Database, PostgresOrganizationUnitOfWorkFactory
from zentra_adapter_postgres.schema import tenants

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)


@pytest.mark.asyncio
async def test_workspace_repository_enforces_names_and_tenant_visibility() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    owner_engine = create_async_engine(OWNER_URL)
    async with owner_engine.begin() as connection:
        await connection.execute(
            insert(tenants),
            [
                {"tenant_id": tenant_id, "name": "Workspace Tenant"},
                {"tenant_id": other_tenant_id, "name": "Other Tenant"},
            ],
        )

    database = Database(RUNTIME_URL)
    service = OrganizationService(
        unit_of_work_factory=PostgresOrganizationUnitOfWorkFactory(database),
        now=lambda: datetime.now(UTC),
        new_id=uuid4,
    )
    actor = AuthenticatedActor(
        user_id=uuid4(),
        tenant_id=tenant_id,
        role=Role.OWNER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )
    other_actor = AuthenticatedActor(
        user_id=uuid4(),
        tenant_id=other_tenant_id,
        role=Role.OWNER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )

    group = await service.create_group(actor, name="Finance Operations")
    await service.create_project(actor, group_id=group.group_id, name="Forecast")
    with pytest.raises(OrganizationNameConflictError):
        await service.create_group(actor, name="  FINANCE   OPERATIONS ")
    with pytest.raises(OrganizationNotFoundError):
        await service.get_group(other_actor, group.group_id)

    await database.close()
    async with owner_engine.begin() as connection:
        await connection.execute(
            tenants.delete().where(
                tenants.c.tenant_id.in_((tenant_id, other_tenant_id))
            )
        )
    await owner_engine.dispose()
