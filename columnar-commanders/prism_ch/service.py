"""A minimal stdlib HTTP surface: /health, /ready, /info.

Deliberately dependency-free - swap in FastAPI or your framework of choice when
the service grows real endpoints.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import __version__
from .config import Settings
from .db import cluster_nodes, connect

log = logging.getLogger(__name__)


def _probe(settings: Settings) -> dict[str, Any]:
    client = connect(settings, database="")
    nodes = cluster_nodes(client, settings.cluster)
    version = client.command("SELECT version()")
    return {
        "clickhouse_version": version,
        "cluster": settings.cluster,
        "nodes": nodes,
    }


class Handler(BaseHTTPRequestHandler):
    settings: Settings  # injected by serve()

    protocol_version = "HTTP/1.1"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        route = self.path.split("?", 1)[0].rstrip("/") or "/"

        if route in {"/", "/health"}:
            self._send(200, {"status": "ok", "version": __version__})
            return

        if route in {"/ready", "/info"}:
            try:
                info = _probe(self.settings)
            except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 503
                self._send(503, {"status": "unavailable", "error": str(exc)})
                return
            self._send(200, {"status": "ok", "version": __version__, **info})
            return

        self._send(404, {"status": "not_found", "path": route})

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def serve(settings: Settings) -> None:
    handler = type("BoundHandler", (Handler,), {"settings": settings})
    server = ThreadingHTTPServer((settings.http_host, settings.http_port), handler)
    log.info("listening on http://%s:%d", settings.http_host, settings.http_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
