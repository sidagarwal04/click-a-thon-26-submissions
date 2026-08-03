from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.services.run_observability import (
    RunObservability,
    RunObservabilityError,
    RunObservabilityNotConfiguredError,
    RunObservabilityNotFoundError,
    get_run_observability,
)

router = APIRouter(prefix="/observability", tags=["observability"])


def provide_run_observability() -> RunObservability:
    try:
        return get_run_observability()
    except RunObservabilityNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/runs")
def list_observability_runs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    service: RunObservability = Depends(provide_run_observability),
) -> dict[str, Any]:
    try:
        return service.list_runs(page=page, limit=limit)
    except RunObservabilityNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RunObservabilityError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/runs/{trace_id}")
def get_observability_run(
    trace_id: str,
    service: RunObservability = Depends(provide_run_observability),
) -> dict[str, Any]:
    try:
        return service.get_run(trace_id)
    except RunObservabilityNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RunObservabilityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RunObservabilityError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
