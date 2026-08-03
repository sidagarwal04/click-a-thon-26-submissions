from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from .database import set_tenant_context
from .schema import (
    identity_subjects,
    tenant_identity_bindings,
    tenant_memberships,
    tenants,
    users,
)


class IdentityNotBoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class IdentityContext:
    user_id: UUID
    tenant_id: UUID
    email: str
    tenant_name: str
    role: str


async def resolve_identity_context(
    connection: AsyncConnection,
    *,
    provider: str,
    external_subject_id: str,
    external_tenant_id: str,
) -> IdentityContext:
    tenant_row = (
        await connection.execute(
            select(tenant_identity_bindings.c.tenant_id).where(
                tenant_identity_bindings.c.provider == provider,
                tenant_identity_bindings.c.external_tenant_id == external_tenant_id,
            )
        )
    ).one_or_none()
    if tenant_row is None:
        raise IdentityNotBoundError("Identity organization is not bound to a tenant")

    await set_tenant_context(connection, tenant_row.tenant_id)
    tenant_name = (
        await connection.execute(
            select(tenants.c.name).where(tenants.c.tenant_id == tenant_row.tenant_id)
        )
    ).scalar_one()
    membership_row = (
        await connection.execute(
            select(
                users.c.user_id,
                users.c.email,
                tenant_memberships.c.role,
            )
            .join(
                identity_subjects,
                identity_subjects.c.user_id == users.c.user_id,
            )
            .join(
                tenant_memberships,
                tenant_memberships.c.user_id == users.c.user_id,
            )
            .where(
                identity_subjects.c.provider == provider,
                identity_subjects.c.external_subject_id == external_subject_id,
                tenant_memberships.c.tenant_id == tenant_row.tenant_id,
            )
        )
    ).one_or_none()
    if membership_row is None:
        raise IdentityNotBoundError("Identity subject has no membership in this tenant")

    return IdentityContext(
        user_id=membership_row.user_id,
        tenant_id=tenant_row.tenant_id,
        email=membership_row.email,
        tenant_name=tenant_name,
        role=membership_row.role,
    )
