"""Shared request-handling helpers for the Connector HTTP surface.

Extracted out of ``connector_routes.py`` so a second router
(``connector_rows_routes.py``) can reuse the same error-mapping/service-lookup/
actor-translation without duplicating them or growing that file past its LOC
budget.
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException, Request, status
from zentra_application_connector import (
    AuthenticatedActor,
    CatalogVersionNotFoundError,
    ConflictError,
    ConnectionFailedError,
    ConnectorService,
    DataSourceNotFoundError,
    HarvestRunNotFoundError,
    PermissionDeniedError,
    RelationNotFoundError,
    Role,
    UploadRejectedError,
)

from .request_context import RequestContext


@contextmanager
def _handle():
    """Map application failures to status codes, in one place.

    Ordered narrowest first. ``ConnectionFailedError`` carries a typed failure
    and nothing from the source's own error text, so the 502 body names which
    field to fix without echoing hostnames or usernames back to the caller.
    """
    try:
        yield
    except PermissionDeniedError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except (
        DataSourceNotFoundError,
        RelationNotFoundError,
        HarvestRunNotFoundError,
        CatalogVersionNotFoundError,
    ) as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except ConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ConnectionFailedError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, error.failure.value
        ) from error
    except UploadRejectedError as error:
        detail: dict[str, object] = {"message": str(error)}
        if error.row is not None:
            detail["row"] = error.row
        if error.column is not None:
            detail["column"] = error.column
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail) from error


def _service(request: Request) -> ConnectorService:
    """The Connector Service, or a 503 saying why there isn't one.

    Absent when `CONNECTOR_CREDENTIAL_KEY` is unset, since without it no
    credential can be sealed. Answering 503 with the missing setting named beats
    the `AttributeError` this used to raise: a 500 with no body reads as a bug in
    the service rather than as configuration nobody supplied.
    """
    service = getattr(request.app.state.dependencies, "connector", None)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Connector is not configured: CONNECTOR_CREDENTIAL_KEY is not set",
        )
    return service


def _actor(context: RequestContext) -> AuthenticatedActor:
    """Re-express the request's actor in the connector's own vocabulary.

    Translated rather than shared: the two application packages each own their
    role enum, and having one import the other's would couple two contexts that
    have no reason to move together.
    """
    return AuthenticatedActor(
        user_id=context.actor.user_id,
        tenant_id=context.actor.tenant_id,
        role=Role(context.actor.role.value),
    )
