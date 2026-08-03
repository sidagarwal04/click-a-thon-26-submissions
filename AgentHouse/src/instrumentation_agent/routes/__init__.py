"""FastAPI route package — aggregate routers for the app host."""

from fastapi import APIRouter

from instrumentation_agent.routes.health import router as health_router
from instrumentation_agent.routes.instrumentation import router as instrumentation_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(instrumentation_router)

__all__ = ["api_router"]
