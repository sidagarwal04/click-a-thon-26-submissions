"""Health interface used by the health router."""

from __future__ import annotations

from instrumentation_agent.db.connection import ping as ping_postgres
from instrumentation_agent.models.schemas import HealthResponse
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import ping_clickhouse


def health_check() -> HealthResponse:
    settings = get_settings()
    status = "ok"
    try:
        ping_postgres()
        postgres = "up"
    except Exception as exc:  # noqa: BLE001
        postgres = f"down: {exc}"
        status = "degraded"
    try:
        ping_clickhouse()
        clickhouse = "up"
    except Exception as exc:  # noqa: BLE001
        clickhouse = f"down: {exc}"
        status = "degraded"
    return HealthResponse(
        status=status,
        postgres=postgres,
        clickhouse=clickhouse,
        specs_root=str(settings.specs_root),
    )
