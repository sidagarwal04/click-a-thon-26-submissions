from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_application_investigation import (
    AuthenticatedActor,
    OrganizationService,
    Role,
    ThreadNotFoundError,
    ThreadService,
)

from zentra_adapter_postgres import (
    Database,
    PostgresOrganizationUnitOfWorkFactory,
    PostgresThreadUnitOfWorkFactory,
)
from zentra_adapter_postgres.schema import (
    investigation_threads,
    tenants,
    thread_messages,
)

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)


def actor(tenant_id) -> AuthenticatedActor:
    return AuthenticatedActor(
        user_id=uuid4(),
        tenant_id=tenant_id,
        role=Role.MEMBER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_thread_and_first_message_are_atomic_and_tenant_scoped() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    owner_engine = create_async_engine(OWNER_URL)
    async with owner_engine.begin() as connection:
        await connection.execute(
            insert(tenants),
            [
                {"tenant_id": tenant_id, "name": "Thread Tenant"},
                {"tenant_id": other_tenant_id, "name": "Other Tenant"},
            ],
        )

    database = Database(RUNTIME_URL)

    def now() -> datetime:
        return datetime.now(UTC)

    organization = OrganizationService(
        unit_of_work_factory=PostgresOrganizationUnitOfWorkFactory(database),
        now=now,
        new_id=uuid4,
    )
    threads = ThreadService(
        unit_of_work_factory=PostgresThreadUnitOfWorkFactory(database),
        now=now,
        new_id=uuid4,
    )
    owner = actor(tenant_id)
    group = await organization.create_group(owner, name="Finance")
    project = await organization.create_project(
        owner, group_id=group.group_id, name="Forecast"
    )

    draft = await threads.create(
        owner, project_id=project.project_id, content="How is the business doing?"
    )

    with pytest.raises(ThreadNotFoundError):
        await threads.get(actor(other_tenant_id), draft.thread_id)
    async with owner_engine.connect() as connection:
        thread_count = await connection.scalar(
            select(func.count())
            .select_from(investigation_threads)
            .where(investigation_threads.c.thread_id == draft.thread_id)
        )
        message_count = await connection.scalar(
            select(func.count())
            .select_from(thread_messages)
            .where(thread_messages.c.thread_id == draft.thread_id)
        )
    assert thread_count == 1
    assert message_count == 2

    await threads.delete(owner, draft.thread_id)
    await database.close()
    async with owner_engine.begin() as connection:
        await connection.execute(
            tenants.delete().where(
                tenants.c.tenant_id.in_((tenant_id, other_tenant_id))
            )
        )
    await owner_engine.dispose()
