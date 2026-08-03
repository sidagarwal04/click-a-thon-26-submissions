"""HTTP surface for the Connector context.

A thin translation layer and nothing more: every decision about what is allowed
lives in ``ConnectorService``, so this module maps application exceptions to
status codes and application read models to wire shapes.

The error mapping is centralised in ``_handle`` rather than repeated per route,
because the mapping is a policy — a permission failure is 403 everywhere, a
lifecycle conflict is 409 everywhere — and scattering it would let one route
disagree with the others.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from zentra_application_connector import (
    AgentAccessView,
    AuthenticatedActor,
    SourceCredentials,
    SourceFieldDescriptor,
)
from zentra_domain_connector import (
    AccessOverrides,
    CatalogAccessOverride,
    HarvestBudget,
    HarvestScope,
    RelationState,
    UploadFormat,
)

from .connector_schemas import (
    AgentAccessResponse,
    CatalogDiffResponse,
    CatalogResponse,
    CommitUploadRequest,
    DeclareRelationRequest,
    DeletionPreviewResponse,
    HarvestResponse,
    JoinGraphResponse,
    RegisterSourceRequest,
    RelationDecisionRequest,
    RelationResponse,
    SetAgentAccessRequest,
    SourceResponse,
    StartHarvestRequest,
    UpdateCredentialsRequest,
    UploadPreviewResponse,
)
from .connector_shared import _actor, _handle, _service
from .request_context import RequestContext, authenticated_context

router = APIRouter(prefix="/v1/connector", tags=["connector"])
AuthenticatedRequest = Annotated[RequestContext, Depends(authenticated_context)]

#: How much of an upload is read to build a preview. Bounded because a preview
#: is meant to be instant and a user cannot read more than this anyway.
PREVIEW_ROWS = 20

#: Streamed in chunks rather than read whole, so a large file does not have to
#: fit in memory before it is rejected for being too large.
UPLOAD_CHUNK_BYTES = 1024 * 1024


def _as_domain(
    actor: AuthenticatedActor, view: AgentAccessView
) -> CatalogAccessOverride:
    """Re-express an access view in the domain's own vocabulary.

    Needed only because `AccessOverrides.build` (the shared filtering logic)
    takes the domain type; the view crossed into the application layer's
    vocabulary on its way out of the service and is translated back here
    rather than duplicating that filtering logic against the view shape.
    """
    return CatalogAccessOverride(
        override_id=view.override_id,
        tenant_id=actor.tenant_id,
        data_source_id=view.data_source_id,
        table_name=view.table_name,
        field_name=view.field_name,
        agent_visible=view.agent_visible,
        decided_by=view.decided_by,
        decided_at=view.decided_at,
    )


# ------------------------------------------------------------------- sources


@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_source(
    request: Request,
    context: AuthenticatedRequest,
    body: RegisterSourceRequest,
) -> SourceResponse:
    with _handle():
        summary = await _service(request).register_source(
            _actor(context),
            name=body.name,
            credentials=SourceCredentials(**body.credentials.model_dump()),
            description=body.description,
            store_sample_values=body.store_sample_values,
        )
    return SourceResponse.from_summary(summary)


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    request: Request, context: AuthenticatedRequest
) -> list[SourceResponse]:
    summaries = await _service(request).list_sources(_actor(context))
    return [SourceResponse.from_summary(s) for s in summaries]


@router.get("/sources/{data_source_id}", response_model=SourceResponse)
async def get_source(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> SourceResponse:
    with _handle():
        summary = await _service(request).get_source(_actor(context), data_source_id)
    return SourceResponse.from_summary(summary)


@router.put("/sources/{data_source_id}/credentials", response_model=SourceResponse)
async def update_credentials(
    request: Request,
    context: AuthenticatedRequest,
    data_source_id: UUID,
    body: UpdateCredentialsRequest,
) -> SourceResponse:
    with _handle():
        summary = await _service(request).update_credentials(
            _actor(context),
            data_source_id,
            credentials=SourceCredentials(**body.credentials.model_dump()),
        )
    return SourceResponse.from_summary(summary)


@router.post("/sources/{data_source_id}/test-connection", response_model=SourceResponse)
async def test_connection(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> SourceResponse:
    with _handle():
        summary = await _service(request).test_connection(
            _actor(context), data_source_id
        )
    return SourceResponse.from_summary(summary)


@router.get(
    "/sources/{data_source_id}/deletion-preview",
    response_model=DeletionPreviewResponse,
)
async def preview_source_deletion(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> DeletionPreviewResponse:
    """What DELETE would destroy, so it is known beforehand.

    A read. Deletion itself stays unconditional — a Tenant who wants their data
    gone should not be argued with, only informed.
    """
    with _handle():
        preview = await _service(request).preview_source_deletion(
            _actor(context), data_source_id
        )
    return DeletionPreviewResponse(
        data_source_id=preview.data_source_id,
        name=preview.name,
        catalog_versions=preview.catalog_versions,
        confirmed_relations=preview.confirmed_relations,
        cross_source_relations=preview.cross_source_relations,
        drops_stored_data=preview.drops_stored_data,
    )


@router.delete("/sources/{data_source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> None:
    with _handle():
        await _service(request).delete_source(_actor(context), data_source_id)


# ------------------------------------------------------------------ harvests


@router.post(
    "/sources/{data_source_id}/harvests",
    response_model=HarvestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_harvest(
    request: Request,
    context: AuthenticatedRequest,
    data_source_id: UUID,
    background: BackgroundTasks,
    body: StartHarvestRequest | None = None,
) -> HarvestResponse:
    """Begin discovery and return something to watch.

    202 rather than 200, and the work is scheduled after the response rather
    than awaited: relation inference issues a query per candidate pair against
    someone else's warehouse and will not finish inside a request.
    """
    payload = body or StartHarvestRequest()
    budget = HarvestBudget()
    if payload.max_queries is not None:
        budget.max_queries = payload.max_queries
    if payload.sample_rows is not None:
        budget.sample_rows = payload.sample_rows

    with _handle():
        started = await _service(request).start_harvest(
            _actor(context),
            data_source_id,
            scope=HarvestScope(
                databases=tuple(payload.databases), tables=tuple(payload.tables)
            ),
            budget=budget,
        )
    background.add_task(
        _service(request).run_harvest, _actor(context), started.harvest_run_id
    )
    return HarvestResponse.from_status(started)


@router.get("/harvests/{harvest_run_id}", response_model=HarvestResponse)
async def get_harvest(
    request: Request, context: AuthenticatedRequest, harvest_run_id: UUID
) -> HarvestResponse:
    with _handle():
        found = await _service(request).get_harvest(_actor(context), harvest_run_id)
    return HarvestResponse.from_status(found)


@router.post("/harvests/{harvest_run_id}/cancel", response_model=HarvestResponse)
async def cancel_harvest(
    request: Request, context: AuthenticatedRequest, harvest_run_id: UUID
) -> HarvestResponse:
    with _handle():
        cancelled = await _service(request).cancel_harvest(
            _actor(context), harvest_run_id
        )
    return HarvestResponse.from_status(cancelled)


@router.get(
    "/sources/{data_source_id}/harvests", response_model=list[HarvestResponse]
)
async def list_harvests(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> list[HarvestResponse]:
    with _handle():
        runs = await _service(request).list_harvests(_actor(context), data_source_id)
    return [HarvestResponse.from_status(r) for r in runs]


# ------------------------------------------------------------------- catalog


@router.get("/sources/{data_source_id}/catalog", response_model=CatalogResponse)
async def latest_catalog(
    request: Request, context: AuthenticatedRequest, data_source_id: UUID
) -> CatalogResponse:
    service = _service(request)
    actor = _actor(context)
    with _handle():
        version = await service.latest_catalog(actor, data_source_id)
        overrides = await service.list_agent_access(actor, data_source_id)
    return CatalogResponse.from_version(
        version,
        overrides=AccessOverrides.build(
            data_source_id, tuple(_as_domain(actor, o) for o in overrides)
        ),
    )


@router.get("/catalog-versions/{catalog_version_id}", response_model=CatalogResponse)
async def get_catalog(
    request: Request, context: AuthenticatedRequest, catalog_version_id: UUID
) -> CatalogResponse:
    service = _service(request)
    actor = _actor(context)
    with _handle():
        version = await service.get_catalog(actor, catalog_version_id)
        overrides = await service.list_agent_access(actor, version.data_source_id)
    return CatalogResponse.from_version(
        version,
        overrides=AccessOverrides.build(
            version.data_source_id,
            tuple(_as_domain(actor, o) for o in overrides),
        ),
    )


@router.get("/catalog-versions/{catalog_version_id}/search")
async def search_catalog(
    request: Request,
    context: AuthenticatedRequest,
    catalog_version_id: UUID,
    q: str,
) -> dict[str, list[str]]:
    with _handle():
        hits = await _service(request).search_catalog(
            _actor(context), catalog_version_id, q
        )
    return {"matches": list(hits)}


@router.get(
    "/catalog-versions/{catalog_version_id}/diff",
    response_model=CatalogDiffResponse,
)
async def diff_catalog(
    request: Request,
    context: AuthenticatedRequest,
    catalog_version_id: UUID,
    against: UUID,
) -> CatalogDiffResponse:
    with _handle():
        report = await _service(request).diff_catalog(
            _actor(context), previous_id=against, current_id=catalog_version_id
        )
    return CatalogDiffResponse(
        catalog_version_id=report.catalog_version_id,
        carried_forward=report.carried_forward,
        staled=report.staled,
        added_fields=report.added_fields,
        removed_fields=report.removed_fields,
        type_changed_fields=report.type_changed_fields,
    )


@router.patch(
    "/sources/{data_source_id}/tables/{table_name}/agent-access",
    response_model=AgentAccessResponse,
)
async def set_table_agent_access(
    request: Request,
    context: AuthenticatedRequest,
    data_source_id: UUID,
    table_name: str,
    body: SetAgentAccessRequest,
) -> AgentAccessResponse:
    with _handle():
        view = await _service(request).set_table_agent_access(
            _actor(context),
            data_source_id,
            table_name,
            agent_visible=body.agent_visible,
        )
    return AgentAccessResponse.from_view(view)


@router.patch(
    "/sources/{data_source_id}/tables/{table_name}/fields/{field_name}/agent-access",
    response_model=AgentAccessResponse,
)
async def set_field_agent_access(
    request: Request,
    context: AuthenticatedRequest,
    data_source_id: UUID,
    table_name: str,
    field_name: str,
    body: SetAgentAccessRequest,
) -> AgentAccessResponse:
    with _handle():
        view = await _service(request).set_field_agent_access(
            _actor(context),
            data_source_id,
            table_name,
            field_name,
            agent_visible=body.agent_visible,
        )
    return AgentAccessResponse.from_view(view)


# ----------------------------------------------------------------- relations


@router.get(
    "/catalog-versions/{catalog_version_id}/relations",
    response_model=list[RelationResponse],
)
async def list_relations(
    request: Request,
    context: AuthenticatedRequest,
    catalog_version_id: UUID,
    state: RelationState | None = None,
) -> list[RelationResponse]:
    with _handle():
        views = await _service(request).list_relations(
            _actor(context), catalog_version_id, state=state
        )
    return [RelationResponse.from_view(v) for v in views]


@router.post("/relations/{relation_id}/decision", response_model=RelationResponse)
async def decide_relation(
    request: Request,
    context: AuthenticatedRequest,
    relation_id: UUID,
    body: RelationDecisionRequest,
) -> RelationResponse:
    """Confirm or reject a proposal.

    A rejection without a reason is refused here rather than defaulted, because
    the reason is what stops the same wrong guess being re-proposed forever and
    a default would silently pick one on the reviewer's behalf.
    """
    service = _service(request)
    actor = _actor(context)
    with _handle():
        if body.decision == "confirm":
            view = await service.confirm_relation(actor, relation_id)
        else:
            if body.reason is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "A rejection must state a reason",
                )
            view = await service.reject_relation(actor, relation_id, reason=body.reason)
    return RelationResponse.from_view(view)


@router.post("/relations/{relation_id}/revoke", response_model=RelationResponse)
async def revoke_relation(
    request: Request, context: AuthenticatedRequest, relation_id: UUID
) -> RelationResponse:
    with _handle():
        view = await _service(request).revoke_relation(_actor(context), relation_id)
    return RelationResponse.from_view(view)


@router.post(
    "/catalog-versions/{catalog_version_id}/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def declare_relation(
    request: Request,
    context: AuthenticatedRequest,
    catalog_version_id: UUID,
    body: DeclareRelationRequest,
) -> RelationResponse:
    with _handle():
        view = await _service(request).declare_relation(
            _actor(context),
            catalog_version_id=catalog_version_id,
            left_field_id=body.left_field_id,
            right_field_id=body.right_field_id,
        )
    return RelationResponse.from_view(view)


@router.get(
    "/catalog-versions/{catalog_version_id}/join-graph",
    response_model=JoinGraphResponse,
)
async def join_graph(
    request: Request, context: AuthenticatedRequest, catalog_version_id: UUID
) -> JoinGraphResponse:
    """The confirmed Relations, and the fields nothing connects to."""
    with _handle():
        view = await _service(request).join_graph(_actor(context), catalog_version_id)
    return JoinGraphResponse.from_view(view)


# ------------------------------------------------------------------- uploads


@router.post(
    "/uploads",
    response_model=UploadPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def preview_upload(
    request: Request,
    context: AuthenticatedRequest,
    file: Annotated[UploadFile, File()],
    upload_format: Annotated[UploadFormat, Form()],
) -> UploadPreviewResponse:
    """Parse a file and show what it looks like, committing to nothing.

    Preview before commit exists because a mis-parsed column discovered after
    the fact has already poisoned every profile and every Relation below it.
    """

    async def stream() -> AsyncIterator[bytes]:
        while chunk := await file.read(UPLOAD_CHUNK_BYTES):
            yield chunk

    with _handle():
        preview = await _service(request).preview_upload(
            _actor(context),
            filename=file.filename or "upload",
            upload_format=upload_format,
            stream=stream(),
            preview_rows=PREVIEW_ROWS,
        )
    return UploadPreviewResponse.from_preview(preview)


@router.post(
    "/uploads/{upload_id}/commit",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def commit_upload(
    request: Request,
    context: AuthenticatedRequest,
    upload_id: UUID,
    body: CommitUploadRequest,
) -> SourceResponse:
    columns = (
        [
            SourceFieldDescriptor(
                name=c.name,
                declared_type=c.declared_type,
                nullable=c.nullable,
                position=c.position,
            )
            for c in body.columns
        ]
        if body.columns
        else None
    )
    with _handle():
        summary = await _service(request).commit_upload(
            _actor(context), upload_id, name=body.name, columns=columns
        )
    return SourceResponse.from_summary(summary)
