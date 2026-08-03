"""HTTP surface for browsing a Source Table's raw rows.

A separate router (not `connector_routes.py`, already at its LOC budget) for
one deliberately narrow endpoint: it reads the confirmed field list off the
latest Catalog Version and queries Cube directly with a hand-built dimension
list, bypassing `CubeSemanticLayer.query()`'s governed-metrics check — see
`connector_rows.py`'s module docstring for why that bypass is safe here and
nowhere else.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from zentra_application_connector import (
    CatalogVersionNotFoundError,
    DataSourceNotFoundError,
)

from .connector_rows import (
    ROW_PAGE_SIZE,
    CubeNotReadyError,
    TableNotInCatalogError,
    build_rows_query,
    find_table,
    parse_rows_payload,
)
from .connector_schemas import TableRowsResponse
from .connector_shared import _actor, _service
from .cube_scope import ScopedCubeSemanticLayers
from .request_context import RequestContext, authenticated_context

router = APIRouter(prefix="/v1/connector", tags=["connector"])
AuthenticatedRequest = Annotated[RequestContext, Depends(authenticated_context)]
PageNumber = Annotated[int, Query(ge=1)]


@contextmanager
def _handle_rows():
    """Errors this route can raise, mapped once rather than per branch.

    A read open to any tenant member — same policy as `latest_catalog` and
    `list_agent_access`, no role gate. `TableNotInCatalogError` and
    `CubeNotReadyError`/`httpx.HTTPError` both answer with a status the
    frontend recognises as "not ready yet" rather than a generic failure —
    see `datasets/api.ts`. Deliberately merged for v1: a stale/mistyped
    table or data-source id reads the same as a genuine sync delay.
    """
    try:
        yield
    except (
        DataSourceNotFoundError,
        CatalogVersionNotFoundError,
        TableNotInCatalogError,
    ) as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except (CubeNotReadyError, httpx.HTTPError) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "This table's data is not reachable yet — it may still be syncing.",
        ) from error


def _cube_semantic_layers(request: Request) -> ScopedCubeSemanticLayers:
    layers = getattr(request.app.state.dependencies, "cube_semantic_layers", None)
    if layers is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Cube is not configured: CUBE_URL is not set",
        )
    return layers


@router.get(
    "/sources/{data_source_id}/tables/{table_name}/rows",
    response_model=TableRowsResponse,
)
async def browse_table_rows(
    request: Request,
    context: AuthenticatedRequest,
    data_source_id: UUID,
    table_name: str,
    page: PageNumber = 1,
) -> TableRowsResponse:
    service = _service(request)
    actor = _actor(context)
    with _handle_rows():
        version = await service.latest_catalog(actor, data_source_id)
        table = find_table(version, table_name)
        query = build_rows_query(table, page=page)
        semantic_layer = await _cube_semantic_layers(request).resolve(
            tenant_id=actor.tenant_id, data_connection_id=data_source_id
        )
        payload = await semantic_layer.load_raw(query)
        columns, rows, total = parse_rows_payload(payload, table)
    return TableRowsResponse(
        data_source_id=data_source_id,
        table_name=table_name,
        columns=columns,
        rows=rows,
        total=total,
        page=page,
        page_size=ROW_PAGE_SIZE,
    )
