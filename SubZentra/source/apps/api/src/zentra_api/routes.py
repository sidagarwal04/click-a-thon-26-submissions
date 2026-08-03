from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from zentra_adapter_telemetry import (
    correlate_investigation,
    record_citation_resolution,
)
from zentra_application_investigation import (
    ConflictError,
    InvestigationNotFoundError,
    PermissionDeniedError,
    ScenarioUnavailableError,
)
from zentra_domain_agent_execution import PublicAgent
from zentra_domain_investigation import Tombstone

from .active_connection import (
    AmbiguousDataConnectionError,
    active_data_connection_id,
)
from .request_context import RequestContext, authenticated_context
from .schemas import (
    ApprovalDecisionRequest,
    CatalogMemberResponse,
    CatalogSummaryResponse,
    ContextResponse,
    DependencyStatus,
    EvidenceCitationResponse,
    EvidenceDeletionRequest,
    InvestigationCreateRequest,
    InvestigationDetailResponse,
    ReadinessResponse,
    TombstoneResponse,
    VisualizationActionRequest,
    VisualizationActionResponse,
    VisualizationResponse,
)

router = APIRouter()
AuthenticatedRequest = Annotated[RequestContext, Depends(authenticated_context)]


async def _active_connection(
    dependencies: object,
    actor: object,
    *,
    requested: UUID | None = None,
) -> UUID | None:
    """The Data Connection a question is asked against, or a 409 to choose."""
    try:
        return await active_data_connection_id(
            dependencies.connector,  # type: ignore[attr-defined]
            actor,  # type: ignore[arg-type]
            requested=requested,
        )
    except AmbiguousDataConnectionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(request: Request) -> JSONResponse:
    dependencies = request.app.state.dependencies
    checks = await asyncio.gather(
        dependencies.database.health(),
        dependencies.audit.health(),
        dependencies.cube.health(),
    )
    names = ("postgres", "clickhouse", "cube")
    statuses = {
        name: DependencyStatus(status="ready" if healthy else "unavailable")
        for name, healthy in zip(names, checks, strict=True)
    }
    thesys_configured = bool(request.app.state.settings.thesys_api_key)
    statuses["thesys"] = DependencyStatus(
        status="ready" if thesys_configured else "unavailable"
    )
    is_ready = all(checks) and thesys_configured
    response = ReadinessResponse(
        status="ready" if is_ready else "degraded",
        dependencies=statuses,
        configuration={
            "clerk": bool(request.app.state.settings.clerk_issuer),
            "e2b": bool(request.app.state.settings.e2b_api_key),
            "thesys": bool(request.app.state.settings.thesys_api_key),
            "telemetry_export": bool(
                request.app.state.settings.otel_exporter_otlp_endpoint
            ),
        },
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK
        if is_ready
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(mode="json"),
    )


@router.get("/v1/context", response_model=ContextResponse)
async def context(
    resolved: AuthenticatedRequest,
) -> ContextResponse:
    identity = resolved.identity
    return ContextResponse(
        user_id=identity.user_id,
        tenant_id=identity.tenant_id,
        email=identity.email,
        tenant_name=identity.tenant_name,
        role=identity.role,
    )


@router.get("/v1/catalog", response_model=CatalogSummaryResponse)
async def catalog(
    request: Request,
    resolved: AuthenticatedRequest,
) -> CatalogSummaryResponse:
    """The governed vocabulary this tenant may ask questions about.

    Resolved per tenant, so it is the tenant's own catalog and never another's
    — the whole reason `ScopedCubeSemanticLayers` exists. Measures and
    dimensions only: no rows, and no physical schema.
    """
    dependencies = request.app.state.dependencies
    semantic_layer = await dependencies.semantic_layers.resolve(
        tenant_id=resolved.actor.tenant_id,
        # The tenant's own connection, not the demo warehouse. Serving the demo
        # catalog here would offer a question the Investigation cannot answer.
        data_connection_id=await _active_connection(dependencies, resolved.actor),
    )
    governed = await semantic_layer.catalog()
    return CatalogSummaryResponse(
        measures=[
            CatalogMemberResponse(
                name=measure.name,
                type=measure.type,
                description=measure.description,
            )
            for measure in governed.measures
        ],
        dimensions=[
            CatalogMemberResponse(
                name=dimension.name,
                type=dimension.type,
                description=dimension.description,
                values=list(dimension.values),
            )
            for dimension in governed.dimensions
        ],
    )


@router.get("/v1/agents", response_model=list[PublicAgent])
async def agents(request: Request, _: AuthenticatedRequest) -> list[PublicAgent]:
    return list(await request.app.state.dependencies.registry.public_agents())


@router.post(
    "/v1/investigations",
    response_model=InvestigationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investigation(
    body: InvestigationCreateRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    dependencies = request.app.state.dependencies
    try:
        detail = await dependencies.investigations.start(
            resolved.actor,
            question=body.question,
            data_connection_id=await _active_connection(
                dependencies, resolved.actor, requested=body.data_connection_id
            ),
        )
    except ValueError as error:
        # Normalisation refused the text — control characters, or nothing left
        # after stripping. `ValueError` rather than a bespoke type because the
        # domain's `normalize_message_content` is what raises it.
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ScenarioUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return InvestigationDetailResponse.from_detail(detail)


@router.get(
    "/v1/investigations/{investigation_id}",
    response_model=InvestigationDetailResponse,
)
async def get_investigation(
    investigation_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    try:
        detail = await request.app.state.dependencies.investigations.get(
            resolved.actor,
            investigation_id,
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return InvestigationDetailResponse.from_detail(detail)


@router.post(
    "/v1/investigations/{investigation_id}/cancel",
    response_model=InvestigationDetailResponse,
)
async def cancel_investigation(
    investigation_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    try:
        detail = await request.app.state.dependencies.investigations.cancel(
            resolved.actor, investigation_id
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return InvestigationDetailResponse.from_detail(detail)


@router.post(
    "/v1/investigations/{investigation_id}/retry",
    response_model=InvestigationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_investigation(
    investigation_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    try:
        detail = await request.app.state.dependencies.investigations.retry(
            resolved.actor, investigation_id
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return InvestigationDetailResponse.from_detail(detail)


@router.get(
    "/v1/investigations/{investigation_id}/visualization",
    response_model=VisualizationResponse,
)
async def investigation_visualization(
    investigation_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> VisualizationResponse:
    try:
        detail = await request.app.state.dependencies.visualizations.for_investigation(
            resolved.actor, investigation_id
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return VisualizationResponse.from_detail(detail)


@router.get(
    "/v1/visualizations/{visualization_id}",
    response_model=VisualizationResponse,
)
async def get_visualization(
    visualization_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> VisualizationResponse:
    try:
        detail = await request.app.state.dependencies.visualizations.get(
            resolved.actor, visualization_id
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return VisualizationResponse.from_detail(detail)


@router.post(
    "/v1/visualizations/{visualization_id}/retry",
    response_model=VisualizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_visualization(
    visualization_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> VisualizationResponse:
    try:
        detail = await request.app.state.dependencies.visualizations.retry(
            resolved.actor, visualization_id
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return VisualizationResponse.from_detail(detail)


@router.post(
    "/v1/visualizations/{visualization_id}/actions/{action_id}/execute",
    response_model=VisualizationActionResponse,
)
async def execute_visualization_action(
    visualization_id: UUID,
    action_id: UUID,
    body: VisualizationActionRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> VisualizationActionResponse:
    # C1-generated parameters are intentionally ignored. The opaque action ID
    # resolves to the server-stored mapping after tenant reauthorization.
    del body
    try:
        result = await request.app.state.dependencies.visualizations.execute_action(
            resolved.actor,
            visualization_id=visualization_id,
            action_id=action_id,
        )
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return VisualizationActionResponse(
        kind=result.kind,
        citation_id=result.citation_id,
        thread_id=result.thread_id,
        investigation_id=result.investigation_id,
    )


@router.get(
    "/v1/investigations/{investigation_id}/citations/{citation_id}",
    response_model=EvidenceCitationResponse | TombstoneResponse,
)
async def resolve_citation(
    investigation_id: UUID,
    citation_id: UUID,
    request: Request,
    resolved: AuthenticatedRequest,
) -> EvidenceCitationResponse | TombstoneResponse:
    """Follow one claim to the evidence behind it.

    Nested under the Investigation so the Investigation's own visibility is
    checked first: a citation id must not become a way to probe an
    Investigation the caller cannot read.

    There is no Tenant parameter, here or anywhere below. Identity comes from
    the verified token, so there is nothing for a caller to supply or override.
    """
    started = perf_counter()
    # Distinct from `inaccessible`: an operator has to be able to tell a denial
    # from a fault, and seeding the denial value would report every database
    # failure as an authorization outcome.
    state = "failed"
    failure_category: str | None = None
    try:
        citation = await request.app.state.dependencies.investigations.resolve_citation(
            resolved.actor,
            investigation_id=investigation_id,
            citation_id=citation_id,
        )
    except InvestigationNotFoundError as error:
        state = "inaccessible"
        failure_category = "not_visible_to_tenant"
        # Same answer for another Tenant's, another Investigation's, and
        # nonexistent. A caller who could tell them apart could confirm that
        # somebody else's evidence exists.
        raise HTTPException(status_code=404, detail="Evidence was not found") from error
    except Exception as error:
        # The class, never the message. "Timed out" and "the column does not
        # exist" are different operator problems and must not collapse into one
        # `failed` bucket, but the message that tells them apart can quote the
        # evidence.
        failure_category = type(error).__name__
        raise
    else:
        if isinstance(citation, Tombstone):
            state = "tombstoned"
            return TombstoneResponse(
                citation_id=citation.citation_id,
                category=citation.category,
                erased_at=citation.erased_at,
            )
        state = citation.state.value
        return EvidenceCitationResponse.from_domain(citation)
    finally:
        record_citation_resolution(
            state=state,
            duration_ms=int((perf_counter() - started) * 1000),
            failure_category=failure_category,
        )


@router.post(
    "/v1/investigations/{investigation_id}/evidence-deletion",
    response_model=InvestigationDetailResponse,
)
async def delete_evidence(
    investigation_id: UUID,
    payload: EvidenceDeletionRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    """Erase a terminal Investigation's evidence.

    The body must name the Investigation the path already names. It is a
    deliberate redundancy: an irreversible action should be impossible to
    trigger by replaying a URL, and a confirmation the client can default to
    would not be a confirmation.
    """
    correlate_investigation(investigation_id)
    if payload.confirm_investigation_id != investigation_id:
        raise HTTPException(
            status_code=422,
            detail="Confirm the investigation whose evidence is being deleted",
        )
    try:
        detail = await request.app.state.dependencies.investigations.delete_evidence(
            resolved.actor,
            investigation_id=investigation_id,
        )
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return InvestigationDetailResponse.from_detail(detail)


@router.post(
    "/v1/investigations/{investigation_id}/approvals/{approval_id}/decision",
    response_model=InvestigationDetailResponse,
)
async def decide_approval(
    investigation_id: UUID,
    approval_id: UUID,
    body: ApprovalDecisionRequest,
    request: Request,
    resolved: AuthenticatedRequest,
) -> InvestigationDetailResponse:
    try:
        detail = await request.app.state.dependencies.investigations.decide(
            resolved.actor,
            investigation_id=investigation_id,
            approval_id=approval_id,
            decision=body.decision,
            rejection_reason=body.reason,
        )
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return InvestigationDetailResponse.from_detail(detail)
