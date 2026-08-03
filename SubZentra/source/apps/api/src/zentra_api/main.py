from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from zentra_adapter_telemetry import TelemetrySettings, configure_telemetry

from .connector_routes import router as connector_router
from .connector_rows_routes import router as connector_rows_router
from .dependencies import AppDependencies
from .internal_cube_routes import router as internal_cube_router
from .routes import router
from .settings import Settings
from .thread_routes import router as thread_router
from .workspace_routes import router as workspace_router


def create_app(
    settings: Settings | None = None,
    dependencies: AppDependencies | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_dependencies = dependencies or AppDependencies.from_settings(
        resolved_settings
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.dependencies = resolved_dependencies
        if hasattr(resolved_dependencies, "start"):
            await resolved_dependencies.start()
        elif hasattr(resolved_dependencies, "audit_delivery"):
            resolved_dependencies.audit_delivery.start()
        yield
        if hasattr(resolved_dependencies, "stop"):
            await resolved_dependencies.stop()
        elif hasattr(resolved_dependencies, "audit_delivery"):
            await resolved_dependencies.audit_delivery.stop()
        if dependencies is None:
            await resolved_dependencies.close()

    async def _validation_error_discloses_nothing(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        """Say what was wrong with a field, never what was in it.

        FastAPI's default handler puts the rejected value in `input`, and
        `ctx` can carry it too. That was harmless while every rejected body
        field was a short opaque key the handler already declined to echo; a
        question is free text now (ADR-0023), so the default would reflect an
        attacker's payload back inside a response this product vouches for.
        The location and the reason are what a caller needs, and it already
        knows what it sent.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": [
                    {
                        "type": item["type"],
                        "loc": [str(part) for part in item["loc"]],
                        "msg": item["msg"],
                    }
                    for item in error.errors()
                ]
            },
        )

    api = FastAPI(
        title="ZentraOS API",
        version="0.1.0",
        lifespan=lifespan,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Traceparent",
            "Tracestate",
            # The Work Feed documents `Last-Event-ID` as a resume cursor, and it
            # is not a CORS-safelisted request header. Without it here the
            # preflight for `/threads/{id}/events` fails and a browser can never
            # reach the stream at all.
            "Last-Event-ID",
        ],
    )
    api.add_exception_handler(
        RequestValidationError,
        _validation_error_discloses_nothing,  # type: ignore[arg-type]
    )
    api.include_router(router)
    api.include_router(connector_router)
    api.include_router(connector_rows_router)
    api.include_router(workspace_router)
    api.include_router(internal_cube_router)
    api.include_router(thread_router)
    configure_telemetry(
        api,
        TelemetrySettings(
            otlp_endpoint=resolved_settings.otel_exporter_otlp_endpoint,
            otlp_headers=resolved_settings.otel_exporter_otlp_headers,
        ),
    )
    return api


app = create_app()
