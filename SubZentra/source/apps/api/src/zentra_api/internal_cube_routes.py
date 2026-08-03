"""Internal HTTP surface Cube's Node process calls to build a tenant's model.

Not tenant-facing: the caller is Cube's own `asyncModule`/`driverFactory`
code, a container this deployment runs itself, never a Tenant's browser.
Guarded by a static shared secret (`CUBE_INTERNAL_API_SECRET`) rather than
the tenant-facing Clerk JWT — see ADR-0016 for why a shared secret is the
right call for a single-host docker-compose deployment rather than mTLS or
a second signed-JWT scheme.

Every response here is a second HTTP consumer of the exact same
`ConnectorService` methods `connector_routes.py`'s own `GET .../join-graph`
route already calls — nothing here is a new capability in that layer, only
a new caller of it.
"""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from .connector_model import ConnectorNotConfiguredError, connector_cube_model

router = APIRouter(prefix="/internal/v1/cube", tags=["internal"])


def _require_internal_secret(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = request.app.state.settings.cube_internal_api_secret
    if not expected:
        # Unconfigured means this deployment never enabled the internal
        # surface — refuse rather than silently accept every caller.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CUBE_INTERNAL_API_SECRET is not configured",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not compare_digest(token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid internal credential")


InternalRequest = Annotated[None, Depends(_require_internal_secret)]


class ConnectorFieldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    cubeType: str  # noqa: N815 - Cube's own model field naming convention
    #: What the harvest observed about this column. Compiled onto the Cube
    #: member so it reaches `/meta`, and from there the governed catalog an
    #: agent reasons over. Never carries sampled values.
    description: str | None = None


class ConnectorTableSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sqlTable: str  # noqa: N815
    fields: tuple[ConnectorFieldModel, ...]
    description: str | None = None


class ConnectorJoinSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fromTable: str  # noqa: N815
    toTable: str  # noqa: N815
    fromField: str  # noqa: N815
    toField: str  # noqa: N815
    relationship: str


class ConnectorClickHouseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str
    port: int
    database: str
    username: str
    password: str
    secure: bool


class ConnectorCubeModelSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationFingerprint: str  # noqa: N815
    clickhouse: ConnectorClickHouseSchema
    tables: tuple[ConnectorTableSchema, ...]
    joins: tuple[ConnectorJoinSchema, ...]


@router.get(
    "/model/{tenant_id}/{data_connection_id}",
    response_model=ConnectorCubeModelSchema,
)
async def get_connector_cube_model(
    tenant_id: UUID,
    data_connection_id: UUID,
    request: Request,
    _internal: InternalRequest,
) -> ConnectorCubeModelSchema:
    connector = request.app.state.dependencies.connector
    try:
        model = await connector_cube_model(
            connector,
            tenant_id=tenant_id,
            data_connection_id=data_connection_id,
        )
    except ConnectorNotConfiguredError as error:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, str(error)
        ) from error
    return ConnectorCubeModelSchema(
        relationFingerprint=model.relation_fingerprint,
        clickhouse=ConnectorClickHouseSchema(**model.clickhouse),
        tables=tuple(
            ConnectorTableSchema(
                name=table.name,
                sqlTable=table.sql_table,
                fields=tuple(
                    ConnectorFieldModel(**field) for field in table.fields
                ),
                description=table.description,
            )
            for table in model.tables
        ),
        joins=tuple(
            ConnectorJoinSchema(
                fromTable=join.from_table,
                toTable=join.to_table,
                fromField=join.from_field,
                toField=join.to_field,
                relationship=join.relationship,
            )
            for join in model.joins
        ),
    )
