"""Realtime dashboard: receives pipeline events over HTTP from any running agent
process and fans them out to connected browsers over a WebSocket.

Separate process from the pipeline runs (scripts/run_*.py) — events cross that
process boundary via POST /events (see dashboard/emitter.py), not in-process
pub/sub, since each spec run is its own `python scripts/run_*.py` invocation.

Run standalone:  uvicorn dashboard.server:app --port 8787
Then open http://localhost:8787/
"""
from __future__ import annotations

import pathlib
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()

_clients: set[WebSocket] = set()
_recent: deque[dict] = deque(maxlen=500)  # replay buffer for browsers that connect mid-run


@app.get("/")
def index():
    return FileResponse(pathlib.Path(__file__).parent / "index.html")


@app.post("/events")
async def post_event(event: dict):
    _recent.append(event)
    dead = []
    for ws in _clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        for event in list(_recent):
            await ws.send_json(event)
        while True:
            await ws.receive_text()  # we don't expect client->server messages, just keep the socket open
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
