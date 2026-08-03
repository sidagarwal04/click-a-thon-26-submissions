"""Postgres engines and Agno SQLTools factory (Option A — read-only catalog)."""

from __future__ import annotations

from functools import lru_cache

from agno.tools.sql import SQLTools
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from context_agent.settings import get_settings


@lru_cache
def get_registry_engine() -> Engine:
    """Read-only SQLAlchemy engine for meta_* + context_* (SQLTools)."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


@lru_cache
def get_writable_engine() -> Engine:
    """Writable engine for DDL (init_schema) and publish_context_version."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_postgres_sql_tools() -> SQLTools:
    """Agno SQLTools bound to the read-only registry engine.

    Other agents may import this factory later without editing this package's host.
    """
    return SQLTools(db_engine=get_registry_engine())
