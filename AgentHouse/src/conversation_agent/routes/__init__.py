"""FastAPI route package for conversation_agent analytics."""

from fastapi import APIRouter

from conversation_agent.routes.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(analytics_router)

__all__ = ["api_router"]
