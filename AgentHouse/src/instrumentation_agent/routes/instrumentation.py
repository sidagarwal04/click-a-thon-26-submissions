"""Instrumentation REST routes — invoke Agno instrumentation workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from instrumentation_agent.agent.orchestration import run_instrumentation_agent
from instrumentation_agent.interfaces.instrumentation import (
    get_registry,
    validate_instrument_request,
)
from instrumentation_agent.models.schemas import (
    InstrumentRequest,
    InstrumentResponse,
    RegistryResponse,
)

router = APIRouter(tags=["instrumentation"])


@router.get("/v1/registry/{feature_id}", response_model=RegistryResponse)
def read_registry(feature_id: str) -> RegistryResponse:
    try:
        return get_registry(feature_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"registry unavailable: {exc}") from exc


@router.post("/v1/instrument", response_model=InstrumentResponse)
def instrument(body: InstrumentRequest) -> InstrumentResponse:
    """Run the Instrumentation Agno workflow on a dataset path + spec.md (or feature_id)."""
    try:
        validate_instrument_request(body)
        return run_instrumentation_agent(body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"instrumentation failed: {exc}") from exc
