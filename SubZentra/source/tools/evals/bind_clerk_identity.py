"""Bind a Clerk organization and user to a ZentraOS tenant and membership.

Signing in to Clerk is not enough. The API resolves every request through
`resolve_identity_context`, which needs two rows that Clerk knows nothing about:

    tenant_identity_bindings   clerk org  -> tenants.tenant_id
    identity_subjects          clerk user -> users.user_id

Without them the browser signs in cleanly and every API call returns 403 with
"Identity organization is not bound to a tenant" — a failure that looks like a
Clerk problem and is not one. This script creates the tenant, the user, the
owner membership, and both bindings.

    uv run python tools/evals/bind_clerk_identity.py \\
        --org org_31yA... --user user_31yB... --email you@example.com

Re-running with the same ids is safe: it reports what already exists rather than
duplicating it. Find both ids in the Clerk dashboard, or read them off the JWT
the browser is sending (`sub` and `org_id`).
"""

from __future__ import annotations

import argparse
import asyncio
import os
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_postgres.schema import (
    identity_subjects,
    tenant_identity_bindings,
    tenant_memberships,
    tenants,
    users,
)

PROVIDER = "clerk"

OWNER_URL = os.environ.get(
    "DATABASE_OWNER_URL",
    "postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control",
)


async def bind(*, org: str, user: str, email: str, name: str, tier: str) -> int:
    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as connection:
        tenant_id = (
            await connection.execute(
                select(tenant_identity_bindings.c.tenant_id).where(
                    tenant_identity_bindings.c.provider == PROVIDER,
                    tenant_identity_bindings.c.external_tenant_id == org,
                )
            )
        ).scalar_one_or_none()

        if tenant_id is None:
            tenant_id = uuid4()
            await connection.execute(
                insert(tenants).values(tenant_id=tenant_id, name=name, model_tier=tier)
            )
            await connection.execute(
                insert(tenant_identity_bindings).values(
                    provider=PROVIDER, external_tenant_id=org, tenant_id=tenant_id
                )
            )
            print(f"tenant   created  {tenant_id}  ({name}, {tier} tier)")
        else:
            print(f"tenant   exists   {tenant_id}")

        user_id = (
            await connection.execute(
                select(identity_subjects.c.user_id).where(
                    identity_subjects.c.provider == PROVIDER,
                    identity_subjects.c.external_subject_id == user,
                )
            )
        ).scalar_one_or_none()

        if user_id is None:
            user_id = uuid4()
            await connection.execute(insert(users).values(user_id=user_id, email=email))
            await connection.execute(
                insert(identity_subjects).values(
                    provider=PROVIDER, external_subject_id=user, user_id=user_id
                )
            )
            print(f"user     created  {user_id}  ({email})")
        else:
            print(f"user     exists   {user_id}")

        existing_role = (
            await connection.execute(
                select(tenant_memberships.c.role).where(
                    tenant_memberships.c.tenant_id == tenant_id,
                    tenant_memberships.c.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if existing_role is None:
            await connection.execute(
                insert(tenant_memberships).values(
                    tenant_id=tenant_id, user_id=user_id, role="owner"
                )
            )
            print("member   created  owner")
        else:
            # Not upgraded silently: a demotion to viewer is usually deliberate.
            print(f"member   exists   {existing_role}")

    await engine.dispose()
    print("\nSigned-in requests from this org will now resolve. Reload the app.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, help="Clerk organization id (org_...)")
    parser.add_argument("--user", required=True, help="Clerk user id (user_...)")
    parser.add_argument("--email", required=True, help="Email to record for the user")
    parser.add_argument("--name", default="Local Development", help="Tenant name")
    parser.add_argument(
        "--tier",
        choices=["free", "premium"],
        default="premium",
        help="Model tier for the tenant. Premium is the tier that can publish.",
    )
    args = parser.parse_args()

    for label, value in (("org", args.org), ("user", args.user)):
        if not value.startswith(f"{label}_"):
            raise SystemExit(
                f"--{label} should look like {label}_..., got {value!r}. "
                "Copy it from the Clerk dashboard or the JWT."
            )

    return asyncio.run(
        bind(
            org=args.org,
            user=args.user,
            email=args.email,
            name=args.name,
            tier=args.tier,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
