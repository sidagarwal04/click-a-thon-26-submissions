"""Minimal FastAPI app: Postgres health only (no Agno agent host)."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from context_agent.db import get_registry_engine

app = FastAPI(
    title="AgentHouse Context Catalog",
    version="0.1.0",
    description="Postgres catalog health + library tools for other agents.",
)


@app.get("/health")
def health() -> dict[str, str]:
    status: dict[str, str] = {"status": "ok", "postgres": "ok"}
    try:
        with get_registry_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — health must not leak secrets
        status["status"] = "degraded"
        status["postgres"] = "error"
        status["postgres_error"] = type(exc).__name__
    return status
