#!/usr/bin/env python3
"""
Atlys schema-timeline web app.

Serves the "Schema changes over time" visualization (PROBLEM_STATEMENT.md §4) as a
tiny self-contained web app — Python standard library only, no pip install, no build
step. The data model is rebuilt on every request from live repo artifacts (see
timeline.py), so the dashboard always reflects the current git history + schema files
+ context changelog.

Routes:
  GET /                 -> static/index.html (the dashboard)
  GET /static/<file>    -> static assets
  GET /api/timeline     -> full JSON model (schemas, events, context versions, totals)
  GET /api/schema/<id>  -> one schema's detail (spec_name)
  GET /api/insights     -> flattened agent-generated insights + confidence distribution
  GET /healthz          -> {"ok": true}

Config (env):
  TIMELINE_HOST   bind host   (default: 127.0.0.1)
  TIMELINE_PORT   bind port   (default: 8777)

Run:  python3 Atlys/schema-timeline/server.py   then open http://127.0.0.1:8777
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import timeline

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"

HOST = os.environ.get("TIMELINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TIMELINE_PORT", "8777"))

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlysSchemaTimeline/1.0"

    # keep the console quiet-ish but useful
    def log_message(self, fmt, *args):  # noqa: N802
        print(f"  [timeline] {self.address_string()} {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"), _CONTENT_TYPES[".json"])

    def _static(self, name: str) -> None:
        # prevent path traversal
        target = (STATIC_DIR / name).resolve()
        if not str(target).startswith(str(STATIC_DIR)) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)

        if path in ("/", "/index.html"):
            self._static("index.html")
            return
        if path == "/healthz":
            self._json({"ok": True})
            return
        if path == "/api/timeline":
            try:
                self._json(timeline.build_model())
            except Exception as exc:  # surface, don't hide
                self._json({"error": str(exc)}, 500)
            return
        if path == "/api/insights":
            try:
                self._json(timeline.build_insights(timeline.build_schemas()))
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return
        if path.startswith("/api/schema/"):
            spec = path[len("/api/schema/") :]
            model = timeline.build_model()
            match = next((s for s in model["schemas"] if s["spec_name"] == spec), None)
            self._json(match if match else {"error": "schema not found", "spec": spec},
                       200 if match else 404)
            return
        if path.startswith("/static/"):
            self._static(path[len("/static/") :])
            return
        self._json({"error": "not found", "path": path}, 404)

    do_HEAD = do_GET  # noqa: N815


def main() -> None:
    if not STATIC_DIR.exists():
        raise SystemExit(f"static dir missing: {STATIC_DIR}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    model = timeline.build_model()
    t = model["totals"]
    print("\n  Atlys — Schema Changes Over Time")
    print(f"  serving http://{HOST}:{PORT}")
    print(
        f"  data: {t['schemas']} schemas, {t['schema_commits']} schema-commits, "
        f"{t['context_versions']} context versions "
        f"({'git ok' if model['is_git_repo'] else 'NO GIT — history empty'})\n"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  bye")
        httpd.shutdown()


if __name__ == "__main__":
    main()
