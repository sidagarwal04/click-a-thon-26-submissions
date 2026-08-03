"""
server.py
---------
OpenAI-compatible HTTP surface so LibreChat can register these agents as a
`custom` endpoint. Each configured agent shows up as a selectable model.

    GET  /v1/models            → agent IDs as models
    POST /v1/chat/completions  → run the agent (stream + non-stream)
    GET  /health

Auth: if AGENT_API_KEY is set, requests must send
`Authorization: Bearer <AGENT_API_KEY>`.
"""

import json
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent import list_agent_ids, run_agent
from supervisor import run_supervisor, supervisor_id, delegate_ids
from langfuse_trace import tracing_enabled


def all_model_ids() -> list[str]:
    """Supervisor first so it is LibreChat's default selection."""
    sup = supervisor_id()
    return ([sup] if sup else []) + list_agent_ids()

app = FastAPI(title="SonyLIV Concurrency Agents (OpenAI-compatible)")
REQUIRED_KEY = os.getenv("AGENT_API_KEY", "").strip()


def _check_auth(request: Request) -> None:
    if not REQUIRED_KEY:
        return
    auth = request.headers.get("authorization", "")
    if auth.replace("Bearer ", "").strip() != REQUIRED_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "supervisor": supervisor_id(),
        "delegates": delegate_ids(),
        "agents": list_agent_ids(),
        "langfuse_tracing": tracing_enabled(),
    }


@app.get("/v1/models")
async def list_models(request: Request):
    _check_auth(request)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": aid, "object": "model", "created": now, "owned_by": "liv"}
            for aid in all_model_ids()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    _check_auth(request)
    body = await request.json()

    model = body.get("model") or all_model_ids()[0]
    messages = body.get("messages", [])
    stream = bool(body.get("stream", False))

    # LibreChat sends the conversation id as `user`; groups Langfuse traces.
    session_id = (
        body.get("user")
        or request.headers.get("x-librechat-conversation-id")
        or None
    )

    try:
        if model == supervisor_id():
            answer = await run_supervisor(messages, session_id=session_id)
        else:
            answer = await run_agent(model, messages, session_id=session_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if not stream:
        return JSONResponse({
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def sse():
        first = {
            "id": completion_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(first)}\n\n"

        for i in range(0, len(answer), 24):
            data = {
                "id": completion_id, "object": "chat.completion.chunk",
                "created": created, "model": model,
                "choices": [{"index": 0, "delta": {"content": answer[i:i + 24]},
                             "finish_reason": None}],
            }
            yield f"data: {json.dumps(data)}\n\n"

        done = {
            "id": completion_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(done)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
