"""Stdlib HTTP server for the UI.

No framework on purpose: the brief puts polished frontends out of scope, and a
dependency-free server keeps the deliverable about the agent loop. It answers
the same JSON the CLI prints, so the two surfaces cannot drift.
"""

from __future__ import annotations

import json
import logging
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..config import Settings
from ..tracing import clear_progress_sink, init_tracing, set_progress_sink, shutdown
from . import api

log = logging.getLogger(__name__)

UI_DIR = pathlib.Path(__file__).parent
STATIC_DIR = UI_DIR / "static"
INDEX = (UI_DIR / "index.html").read_bytes()

CONTENT_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

# Schema design and analysis both call an LLM; a browser POST can legitimately
# take a minute.
GET_ROUTES = {
    "/health": lambda _settings: {"ok": True},
    "/ready": api.health,
    "/api/health": api.health,
    "/api/dashboard": api.dashboard,
    "/api/context": api.context,
    "/api/schema-history": api.schema_history,
}
POST_ROUTES = {
    "/api/instrument": api.instrument,
    "/api/analyze": api.analyze,
    "/api/context-refresh": api.context_refresh,
    "/api/context-search": api.context_search,
    "/api/schema/reset": api.reset_local,
}

# Same handlers as POST_ROUTES, called from inside an SSE response instead of
# a single JSON one - so the UI can render each agent step (profile, design,
# validate, ...) live instead of only after the whole run finishes. One
# process-wide dict, not per-handler, because the streamed and non-streamed
# forms must never drift onto two different code paths.
STREAM_ROUTES = {
    "/api/instrument/stream": api.instrument,
    "/api/analyze/stream": api.analyze,
    "/api/context-refresh/stream": api.context_refresh,
}


class Handler(BaseHTTPRequestHandler):
    settings: Settings
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload, default=str).encode(), "application/json")

    def _static(self, route: str) -> bool:
        """Serve a file under /static/. Returns False if the route isn't ours.

        Read fresh off disk on every request rather than cached at import
        time like INDEX - these are edited far more often while iterating on
        the UI, and this server is a dev tool, not one under load.
        """
        if not route.startswith("/static/"):
            return False
        rel = route[len("/static/") :]
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents or not target.is_file():
            self._json({"error": "not found"}, 404)
            return True
        content_type = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), content_type)
        return True

    def do_GET(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0].rstrip("/") or "/"
        if route == "/":
            self._send(200, INDEX, "text/html; charset=utf-8")
            return
        if self._static(route):
            return
        handler = GET_ROUTES.get(route)
        if not handler:
            self._json({"error": "not found"}, 404)
            return
        self._json(handler(self.settings))

    def _read_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": f"bad request body: {exc}"}, 400)
            return None

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0].rstrip("/")

        stream_handler = STREAM_ROUTES.get(route)
        if stream_handler:
            body = self._read_body()
            if body is not None:
                self._stream(stream_handler, body)
            return

        handler = POST_ROUTES.get(route)
        if not handler:
            self._json({"error": "not found"}, 404)
            return
        body = self._read_body()
        if body is None:
            return
        try:
            self._json(handler(self.settings, body))
        except Exception as exc:  # noqa: BLE001 - a failed run is a response, not a 500
            log.exception("%s failed", route)
            self._json({"error": str(exc)[:1200]}, 200)

    def _stream(self, handler: Any, body: dict[str, Any]) -> None:
        """Run `handler` under an SSE response, forwarding live step events.

        No Content-Length and no chunked encoding - the response ends when the
        connection closes, which is what `Connection: close` plus a stdlib
        server (no built-in chunked writer) makes the simplest reliable
        framing here. One request, one run: HTTP/1.1 keep-alive would let the
        next request pipeline onto a socket this handler no longer owns.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(event: dict[str, Any]) -> None:
            chunk = f"data: {json.dumps(event, default=str)}\n\n".encode()
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser navigated away mid-run; the agent keeps going

        token = set_progress_sink(emit)
        try:
            result = handler(self.settings, body)
            emit({"type": "done", "result": result})
        except Exception as exc:  # noqa: BLE001 - reported to the client, not raised
            log.exception("%s failed", self.path)
            emit({"type": "error", "message": str(exc)[:1200]})
        finally:
            clear_progress_sink(token)

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def serve_ui(settings: Settings) -> int:
    init_tracing(settings)
    handler = type("BoundHandler", (Handler,), {"settings": settings})
    server = ThreadingHTTPServer((settings.http_host, settings.http_port), handler)
    log.info(
        "UI on http://localhost:%d -> %s/%s (%s)",
        settings.http_port,
        settings.host,
        settings.database,
        settings.clickhouse_target,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
        shutdown()
    return 0
