"""Health route — thin wrapper over interfaces.health."""

from __future__ import annotations

from fastapi import APIRouter

from instrumentation_agent.interfaces.health import health_check
from instrumentation_agent.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return health_check()
