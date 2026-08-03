from fastapi import APIRouter

from app.api.routes import asklys, observability, pipeline, utils

api_router = APIRouter()
api_router.include_router(utils.router)
api_router.include_router(pipeline.router)
api_router.include_router(observability.router)
api_router.include_router(asklys.router)
