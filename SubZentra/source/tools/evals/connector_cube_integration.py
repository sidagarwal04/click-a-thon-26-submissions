"""Prove the Cube <-> ClickHouse path end to end, against real services.

Registers this repo's own TPC-H ClickHouse database
(`infra/clickhouse/init/002_tpch.sql`, seeded exactly for this purpose) as a
real Data Source, harvests it, confirms one of TPC-H's documented foreign
keys, then queries it through a real, running Cube instance. Every step uses
the actual production code path — `ConnectorService` over real Postgres
adapters, the real `AesGcmCredentialCipher`, the real
`connector_model.relation_fingerprint`/`cube_auth.mint_cube_token` — the same
functions `apps/api` itself calls. Nothing here is mocked.

A pass proves the whole chain a Tenant's pasted ClickHouse credentials travel
through: encrypt at rest -> decrypt in `resolve_driver_credentials` -> Cube's
internal callback (`GET /internal/v1/cube/model/...`) -> `driverFactory`
opens a real `type: 'clickhouse'` connection -> the ClickHouse driver
actually executes a query and returns rows.

Run:  docker compose up -d --wait control-postgres clickhouse cube
      Set DATABASE_OWNER_URL (see README's "Local foundation"), then:
        npm exec -- nx run postgres:migrate
      npm exec -- nx serve api  # separate terminal; needs CONNECTOR_CREDENTIAL_KEY set
      uv run python tools/evals/connector_cube_integration.py

Reads provider-agnostic config from the environment or `apps/api/.env`.
Never prints a credential.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_clickhouse import (
    AesGcmCredentialCipher,
    ClickHouseLandingZone,
    ClickHouseSourceConnector,
)
from zentra_adapter_cube import CubeClient
from zentra_adapter_postgres import (
    Database,
    PostgresAgentAccessRepository,
    PostgresCatalogRepository,
    PostgresDataSourceRepository,
    PostgresHarvestRunRepository,
    PostgresRelationRepository,
)
from zentra_adapter_postgres.schema import tenant_memberships, tenants, users
from zentra_api.connector_model import relation_fingerprint
from zentra_api.cube_auth import mint_cube_token
from zentra_api.settings import Settings
from zentra_application_connector import (
    AuthenticatedActor,
    ConnectorService,
    Role,
    SourceCredentials,
)
from zentra_domain_connector import HarvestBudget, HarvestPhase, HarvestScope

#: Same fixture and same defaults `tools/evals/connector_accuracy.py` already
#: uses, so both scripts point at one TPC-H target and cannot drift apart.
TPCH_CREDENTIALS = SourceCredentials(
    host=os.getenv("TPCH_HOST", "localhost"),
    port=int(os.getenv("TPCH_PORT", "8123")),
    database=os.getenv("TPCH_DATABASE", "tpch"),
    username=os.getenv("TPCH_USERNAME", "tpch_reader"),
    password=os.getenv("TPCH_PASSWORD", "tpch_reader"),
    secure=os.getenv("TPCH_SECURE", "false").lower() == "true",
)

#: One of TPC-H's documented foreign keys (also this repo's ground truth in
#: connector_accuracy.py) — confirmed here so Cube has at least one join to
#: compile, though this script only queries a single table's own count.
RELATION_TO_CONFIRM = frozenset({"orders.o_custkey", "customer.c_custkey"})

OWNER_URL = os.environ.get(
    "DATABASE_OWNER_URL",
    "postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control",
)


class _UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


async def seed_tenant() -> tuple[UUID, UUID]:
    """A tenant, a user, and an owner membership. Duplicated from
    `live_run.py` rather than imported — same small-boundary duplication
    this repo already accepts between `cube.js` and `Connector.js`."""
    tenant_id, user_id = uuid4(), uuid4()
    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as connection:
        await connection.execute(
            insert(tenants).values(
                tenant_id=tenant_id,
                name="Cube/ClickHouse integration check",
                model_tier="free",
            )
        )
        await connection.execute(
            insert(users).values(user_id=user_id, email=f"{user_id}@integration.test")
        )
        await connection.execute(
            insert(tenant_memberships).values(
                tenant_id=tenant_id, user_id=user_id, role="owner"
            )
        )
    await engine.dispose()
    return tenant_id, user_id


def _relation_key(left: str, right: str) -> frozenset[str]:
    # RelationView.left/.right are "table.field:type" — the fingerprint used
    # for matching here is just "table.field".
    return frozenset({left.split(":")[0], right.split(":")[0]})


async def main() -> int:
    settings = Settings()
    if not settings.connector_credential_key:
        print(
            "FAIL  CONNECTOR_CREDENTIAL_KEY is not set — set it the same way "
            "apps/api/.env or docker-compose.yml's api service does."
        )
        return 1

    print("seeding a tenant...")
    tenant_id, user_id = await seed_tenant()
    actor = AuthenticatedActor(user_id=user_id, tenant_id=tenant_id, role=Role.OWNER)

    database = Database(settings.database_url)
    connector = ConnectorService(
        sources=PostgresDataSourceRepository(database),
        catalogs=PostgresCatalogRepository(database),
        relations=PostgresRelationRepository(database),
        runs=PostgresHarvestRunRepository(database),
        access=PostgresAgentAccessRepository(database),
        connector=ClickHouseSourceConnector(),
        cipher=AesGcmCredentialCipher(bytes.fromhex(settings.connector_credential_key)),
        landing_zone=ClickHouseLandingZone(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
            secure=settings.clickhouse_secure,
        ),
        clock=_UtcClock(),
    )

    print(f"registering the TPC-H database ({TPCH_CREDENTIALS.host}:{TPCH_CREDENTIALS.port})...")
    source = await connector.register_source(
        actor, name="TPC-H integration check", credentials=TPCH_CREDENTIALS
    )
    data_source_id = source.data_source_id

    print("harvesting...")
    started = await connector.start_harvest(
        actor,
        data_source_id,
        scope=HarvestScope(databases=(TPCH_CREDENTIALS.database,)),
        budget=HarvestBudget(),
    )
    finished = await connector.run_harvest(actor, started.harvest_run_id)
    if finished.phase != HarvestPhase.COMPLETED:
        print(f"FAIL  harvest ended in phase {finished.phase.value}, not completed")
        await database.close()
        return 1
    print(
        f"  {finished.tables_found} tables, {finished.fields_described} fields, "
        f"{finished.relations_proposed} relations proposed"
    )

    catalog = await connector.latest_catalog(actor, data_source_id)
    proposed = await connector.list_relations(actor, catalog.catalog_version_id)
    match = next(
        (r for r in proposed if _relation_key(r.left, r.right) == RELATION_TO_CONFIRM),
        None,
    )
    if match is None:
        print(f"FAIL  {sorted(RELATION_TO_CONFIRM)} was not proposed by inference")
        await database.close()
        return 1

    print(f"confirming {sorted(RELATION_TO_CONFIRM)}...")
    await connector.confirm_relation(actor, match.relation_id)

    print("computing the relation fingerprint and minting a Cube token...")
    fingerprint = await relation_fingerprint(
        connector, tenant_id=tenant_id, data_connection_id=data_source_id
    )
    token = mint_cube_token(
        str(tenant_id), str(data_source_id), fingerprint, secret=settings.cube_api_secret
    )

    print(f"querying orders.count through Cube ({settings.cube_url})...")
    client = CubeClient(settings.cube_url, token)
    try:
        result = await client.load({"measures": ["orders.count"]})
    except Exception as error:  # noqa: BLE001 - this script's whole point is to surface it
        print(f"FAIL  Cube query failed: {error}")
        await database.close()
        return 1

    rows = result.get("data", [])
    count = int(rows[0]["orders.count"]) if rows else 0
    await database.close()

    if count <= 0:
        print(f"FAIL  orders.count came back as {count}, expected TPC-H's real row count")
        return 1

    print(f"\nPASS  orders.count = {count}")
    print(
        "The full path works: encrypted credentials -> decrypted by "
        "ConnectorService -> Cube's internal callback -> driverFactory -> "
        "a real ClickHouse query, executed and returned."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
