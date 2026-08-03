from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from zentra_adapter_postgres import (
    IdentityContext,
    IdentityNotBoundError,
    resolve_identity_context,
)
from zentra_adapter_telemetry import correlate_tenant, current_trace_ids
from zentra_application_investigation import AuthenticatedActor, Role

from .auth import AuthenticationError, bearer_token


@dataclass(frozen=True, slots=True)
class RequestContext:
    identity: IdentityContext
    actor: AuthenticatedActor


async def authenticated_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> RequestContext:
    try:
        token = bearer_token(authorization)
        principal = await request.app.state.dependencies.jwt_verifier.verify(token)
        async with request.app.state.dependencies.database.engine.begin() as connection:
            identity = await resolve_identity_context(
                connection,
                provider="clerk",
                external_subject_id=principal.subject_id,
                external_tenant_id=principal.organization_id,
            )
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    except IdentityNotBoundError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    correlate_tenant(identity.tenant_id)
    trace_id, span_id = current_trace_ids()
    return RequestContext(
        identity=identity,
        actor=AuthenticatedActor(
            user_id=identity.user_id,
            tenant_id=identity.tenant_id,
            role=Role(identity.role),
            trace_id=trace_id,
            span_id=span_id,
        ),
    )
