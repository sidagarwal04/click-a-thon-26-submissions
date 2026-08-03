"""ClickHouse client helpers."""

from __future__ import annotations

import logging
import time
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from .config import Settings

log = logging.getLogger(__name__)


def _ca_bundle() -> str | None:
    """Path to a CA bundle, or None to let the driver use the system store.

    Python installed from python.org on macOS ships no root certificates, so a
    TLS connection to ClickHouse Cloud fails with CERTIFICATE_VERIFY_FAILED
    until someone runs Install Certificates.command. Pointing at certifi makes
    a host-side run behave the same as one inside the container.
    """
    try:
        import certifi
    except ImportError:  # pragma: no cover - certifi ships with the driver's deps
        return None
    return certifi.where()


def connect(settings: Settings, database: str | None = None) -> Client:
    """Open a client. Pass database='' to connect before the database exists."""
    return clickhouse_connect.get_client(
        host=settings.host,
        port=settings.port,
        username=settings.user,
        password=settings.password,
        database=settings.database if database is None else database,
        secure=settings.secure,
        connect_timeout=settings.connect_timeout,
        ca_cert=_ca_bundle() if settings.secure else None,
    )


def wait_for_clickhouse(
    settings: Settings,
    timeout: float = 120.0,
    interval: float = 2.0,
) -> Client:
    """Poll until the server answers, or raise once `timeout` is exhausted.

    Compose's healthcheck already gates startup, but a bare `make run` against a
    freshly booted server still needs this.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            client = connect(settings, database="")
            client.command("SELECT 1")
            log.info("connected to ClickHouse at %s", settings.dsn)
            return client
        except Exception as exc:  # noqa: BLE001 - driver raises a wide range here
            last_error = exc
            log.debug("ClickHouse not ready yet: %s", exc)
            time.sleep(interval)

    raise TimeoutError(
        f"ClickHouse at {settings.host}:{settings.port} not ready after {timeout:.0f}s"
    ) from last_error


def cluster_nodes(client: Client, cluster: str) -> list[dict[str, Any]]:
    """Rows from system.clusters for `cluster` - empty if it is not configured."""
    result = client.query(
        """
        SELECT cluster, shard_num, replica_num, host_name, port, is_local
        FROM system.clusters
        WHERE cluster = {cluster:String}
        ORDER BY shard_num, replica_num
        """,
        parameters={"cluster": cluster},
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]
