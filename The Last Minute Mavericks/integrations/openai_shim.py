"""OpenAI-compatible shim: LibreChat front-end → RootCauseOS RCA brain.

A tiny stdlib HTTP server that exposes the evidence-grounded analyst
(ui.llm.chat_reply — openai → ollama → deterministic chain, numeric
validator enforced) behind the two endpoints LibreChat needs:

    POST /v1/chat/completions   (JSON, or SSE when "stream": true)
    GET  /v1/models             (one model: rootcauseos-rca)

Run it:  python integrations/openai_shim.py     (port 8601, env SHIM_PORT)

LibreChat custom-endpoint config — paste into librechat.yaml:

    endpoints:
      custom:
        - name: "RootCauseOS RCA"
          baseURL: "http://host.docker.internal:8601/v1"
          apiKey: "any"
          models:
            default: ["rootcauseos-rca"]
            fetch: false
          titleConvo: false

Bearer auth: any token is accepted (presence is logged, the value never is).
Every answer stays constrained to the incident's evidence store, and numeric
claims are validated before they leave this process.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MODEL_ID = "rootcauseos-rca"
DEFAULT_PORT = 8601


def _port() -> int:
    try:
        return int(os.environ.get("SHIM_PORT") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def _load_bundle(incident: str | None = None) -> dict:
    from ui import bundle as B

    return B.load(incident=incident, fresh_api=True)


def _answer(question: str, incident: str | None = None) -> dict:
    from ui import llm

    return llm.chat_reply(_load_bundle(incident), question)


class _Handler(BaseHTTPRequestHandler):
    server_version = "RootCauseOS-Shim/1.0"

    # -------------------------------------------------------------- helpers

    def log_message(self, fmt: str, *args: object) -> None:  # compact log line
        sys.stderr.write("[shim] " + (fmt % args) + "\n")

    def _json(self, status: int, doc: dict) -> None:
        body = json.dumps(doc).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 — CORS preflight (dashboard chat dock)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _note_auth(self) -> None:
        """Accept any bearer token; log presence only — NEVER the value."""
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            self.log_message("bearer token presented (accepted; value not logged)")

    # ------------------------------------------------------------ endpoints

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        if self.path.split("?")[0].rstrip("/") == "/v1/models":
            self._note_auth()
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "rootcauseos",
                        }
                    ],
                },
            )
            return
        self._json(404, {"error": {"message": f"unknown path {self.path}", "type": "invalid_request_error"}})

    def _sse(self, text: str) -> None:
        """Stream one completed answer as OpenAI-style SSE chunks."""
        cid = f"chatcmpl-rcos-{uuid.uuid4().hex[:24]}"
        base = {"id": cid, "object": "chat.completion.chunk",
                "created": int(time.time()), "model": MODEL_ID}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def emit(delta: dict, finish: str | None = None) -> None:
            chunk = dict(base)
            chunk["choices"] = [{"index": 0, "delta": delta, "finish_reason": finish}]
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            emit({"role": "assistant", "content": ""})
            words = text.split(" ")
            for i in range(0, len(words), 6):
                emit({"content": (" " if i else "") + " ".join(words[i:i + 6])})
            emit({}, finish="stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away mid-stream — nothing to salvage

    def do_POST(self) -> None:  # noqa: N802 — http.server API
        if self.path.split("?")[0].rstrip("/") != "/v1/chat/completions":
            self._json(404, {"error": {"message": f"unknown path {self.path}", "type": "invalid_request_error"}})
            return
        self._note_auth()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            doc = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json(400, {"error": {"message": "request body is not valid JSON", "type": "invalid_request_error"}})
            return
        messages = doc.get("messages") or []
        question = next(
            (str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        if not question.strip():
            self._json(400, {"error": {"message": "no user message found in messages[]", "type": "invalid_request_error"}})
            return
        # Which incident is this question about? The dashboard chat dock sends rcos_incident
        # (the card the user clicked); generic OpenAI clients (LibreChat) omit it → top incident.
        # dock sends the clicked card's id; a generic question (FAB / LibreChat) has none →
        # "worst" so we anchor to the biggest actual move, not whichever incident sorts first.
        incident = doc.get("rcos_incident") or "worst"
        try:
            if question.strip() == "__demo_fabrication__":
                from ui import llm as _llm
                reply = _llm.demo_fabrication(_load_bundle(incident))
            else:
                reply = _answer(question, incident)
        except Exception as e:  # noqa: BLE001 — surface as an API error, never a crash
            self._json(500, {"error": {"message": f"rca backend error: {e}", "type": "server_error"}})
            return
        if doc.get("stream"):
            # LibreChat's chat path REQUIRES SSE when it sends stream:true —
            # a plain JSON body renders as an empty message. The answer is
            # already complete, so stream it in word-sized chunks.
            self._sse(reply["text"])
            return
        self._json(
            200,
            {
                "id": f"chatcmpl-rcos-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply["text"]},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )


def main() -> None:
    port = _port()
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    sys.stderr.write(f"[shim] RootCauseOS OpenAI shim listening on :{port} (model {MODEL_ID})\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
