from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            pool_pre_ping=True,
        )

    async def close(self) -> None:
        await self.engine.dispose()

    async def health(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @asynccontextmanager
    async def tenant_connection(
        self, tenant_id: UUID
    ) -> AsyncIterator[AsyncConnection]:
        async with self.engine.begin() as connection:
            await set_tenant_context(connection, tenant_id)
            yield connection


async def set_tenant_context(connection: AsyncConnection, tenant_id: UUID) -> None:
    await connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
