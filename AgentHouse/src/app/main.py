"""Shared FastAPI host for AgentHouse agents.

Start (clickathon venv): ``uvicorn app.main:app --reload --port 8000``
Init DB: ``python -m instrumentation_agent.init_db``
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from conversation_agent.routes import api_router as conversation_api_router
from instrumentation_agent.db.connection import apply_meta_registry_ddl
from instrumentation_agent.routes import api_router as instrumentation_api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        apply_meta_registry_ddl()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] meta registry DDL skipped: {exc}")
    yield


app = FastAPI(
    title="Click-a-thon AgentHouse",
    version="0.1.0",
    description="FastAPI host for Agno AgentOS agents (Instrumentation, Context, Conversation).",
    lifespan=lifespan,
)

app.include_router(instrumentation_api_router)
app.include_router(conversation_api_router)
