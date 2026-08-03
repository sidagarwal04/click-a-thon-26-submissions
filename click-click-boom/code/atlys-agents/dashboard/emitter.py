"""Best-effort event emitter used by tracing/langfuse_wrapper.py to feed the
realtime dashboard. Same optional-integration pattern as hyperdx_integration.py:
if the dashboard server isn't running, this fails silently and the pipeline is
unaffected — it is purely an observability side-channel, never load-bearing.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import requests

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8787")
_TIMEOUT_S = 0.5

# Opt-in second channel: analytics-dashboard's /api/ingest route spawns this
# pipeline as a subprocess and already forwards ANY stdout line that parses as
# JSON with a non-"result" `type` straight through its SSE stream to the
# browser (see route.ts's `sendEvent(parsed)` passthrough) -- no Node-side
# change needed, just print here when asked to. Gated behind an env var so a
# normal `python scripts/run_*.py` from a terminal doesn't get its stdout
# spammed with one JSON blob per trace event (still gets the final
# `print(json.dumps(result))` unaffected).
_STDOUT_TRACE_EVENTS = os.environ.get("EMIT_TRACE_EVENTS_STDOUT") == "1"


def emit_event(event: dict[str, Any]) -> None:
    """Fire-and-forget POST, off the calling thread so a slow/dead dashboard
    server never adds latency to an agent call."""
    event = dict(event)
    event.setdefault("ts", time.time())
    threading.Thread(target=_post, args=(event,), daemon=True).start()
    if _STDOUT_TRACE_EVENTS:
        print(json.dumps({**event, "type": "trace_event"}, default=str), flush=True)


def _post(event: dict[str, Any]) -> None:
    try:
        requests.post(f"{_DASHBOARD_URL}/events", json=event, timeout=_TIMEOUT_S)
    except Exception:
        pass
