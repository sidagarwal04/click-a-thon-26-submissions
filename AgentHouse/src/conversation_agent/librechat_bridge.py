"""OpenAI-compatible bridge so LibreChat can talk to the Visualization Agent.

High-level progress → LibreChat Reasoning panel (``reasoning_content``).
Deep traces → Langfuse (``agno-dev``) via Agno/OpenInference.

Does **not** replace ``visualization_agent.py --os``.

Run:

    python -m conversation_agent.librechat_bridge
    python -m conversation_agent.librechat_bridge --port 7780
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from conversation_agent import config
from conversation_agent.shared import build_mcp_tools
from conversation_agent.visualization_agent import (
    LEGACY_AGENT_ID,
    build_visualization_workflow,
)
from conversation_agent.visualization_agent_old import build_agent as build_legacy_agent

try:
    from agno.db.sqlite import SqliteDb
except ImportError:  # pragma: no cover
    SqliteDb = None  # type: ignore[assignment,misc]

DEFAULT_PORT = 7780
WORKFLOW_MODEL_ID = config.WORKFLOW_ID
LEGACY_MODEL_ID = LEGACY_AGENT_ID

_mcp_tools: Any = None
_legacy_agent: Any = None
_workflow: Any = None

Channel = Literal["reasoning", "content"]

STEP_LABELS = {
    "discover_schema": "Discovering relevant schema",
    "pack_for_plan_visualization": "Packing question + schema for planner",
    "plan_visualization": "Planning visualization",
    "run_analytics": "Running analytics (template SQL / LLM+MCP fallback)",
    "generate_query": "Generating ClickHouse SQL",
    "execute": "Executing query via ClickHouse MCP",
}


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if hasattr(content, "model_dump"):
        return json.dumps(content.model_dump(mode="json"), indent=2, default=str)
    if isinstance(content, dict):
        return json.dumps(content, indent=2, default=str)
    return str(content)


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = str(msg.get("role") or "user").strip().lower()
        content = msg.get("content")
        if isinstance(content, list):
            texts = [
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") in (None, "text")
            ]
            content = "\n".join(t for t in texts if t)
        text = str(content or "").strip()
        if not text:
            continue
        if role == "system":
            parts.append(f"[system]\n{text}")
        elif role == "assistant":
            parts.append(f"[assistant]\n{text}")
        else:
            parts.append(text)
    if not parts:
        raise HTTPException(status_code=400, detail="No usable message content")
    return "\n\n".join(parts)


def _event_name(event: Any) -> str:
    raw = getattr(event, "event", None)
    if raw is None:
        return type(event).__name__
    return str(getattr(raw, "value", raw))


def _tool_name(event: Any) -> str:
    tool = getattr(event, "tool", None)
    if tool is None:
        return "tool"
    return (
        getattr(tool, "tool_name", None)
        or getattr(tool, "name", None)
        or "tool"
    )


def _high_level_progress(event: Any) -> str | None:
    """Map Agno run/workflow events → short LibreChat reasoning lines.

    Keep this high-level; Langfuse holds the deep trace.
    """
    name = _event_name(event)

    if name in ("WorkflowStarted",):
        return "Starting visualization workflow\n"
    if name in ("WorkflowCompleted",):
        return "Workflow finished\n"
    if name in ("WorkflowError", "RunError"):
        err = getattr(event, "error", None) or getattr(event, "content", None)
        return f"Error: {err}\n"

    if name == "StepStarted":
        step = getattr(event, "step_name", None) or "step"
        label = STEP_LABELS.get(str(step), str(step))
        return f"→ {label}\n"
    if name == "StepCompleted":
        step = getattr(event, "step_name", None) or "step"
        label = STEP_LABELS.get(str(step), str(step))
        return f"✓ {label}\n"
    if name == "StepError":
        step = getattr(event, "step_name", None) or "step"
        err = getattr(event, "error", None) or ""
        return f"✗ {step} failed{(': ' + str(err)) if err else ''}\n"

    if name == "RunStarted":
        agent = getattr(event, "agent_name", None) or getattr(event, "agent_id", None)
        return f"Agent run started{f' ({agent})' if agent else ''}\n"
    if name == "ToolCallStarted":
        return f"Calling tool: {_tool_name(event)}\n"
    if name == "ToolCallCompleted":
        return f"Tool done: {_tool_name(event)}\n"
    if name == "ToolCallError":
        err = getattr(event, "error", None) or ""
        return f"Tool error ({_tool_name(event)}): {err}\n"
    if name == "ReasoningStarted":
        return "Model reasoning…\n"
    if name in ("ReasoningStep", "ReasoningContentDelta"):
        text = getattr(event, "reasoning_content", None) or ""
        if text:
            return text if text.endswith("\n") else f"{text}\n"
        return None
    if name == "ReasoningCompleted":
        return "Reasoning complete\n"

    return None


def _final_content_from_event(event: Any) -> str | None:
    name = _event_name(event)
    if name in ("WorkflowCompleted", "RunCompleted"):
        content = getattr(event, "content", None)
        if content is None and hasattr(event, "run_output"):
            content = getattr(event.run_output, "content", None)
        if content is not None:
            return _content_to_text(content)
    return None


async def _iter_model_events(
    model: str,
    prompt: str,
    *,
    session_id: str | None,
) -> AsyncIterator[tuple[Channel, str]]:
    """Yield (channel, text) — reasoning for progress, content for the answer."""
    if model == LEGACY_MODEL_ID:
        if _legacy_agent is None:
            raise HTTPException(status_code=503, detail="Legacy agent not ready")
        yield ("reasoning", "Starting visualization agent\n")
        stream = _legacy_agent.arun(
            prompt,
            session_id=session_id,
            stream=True,
            stream_events=True,
        )
        final = ""
        async for event in stream:
            progress = _high_level_progress(event)
            if progress:
                yield ("reasoning", progress)
            maybe_final = _final_content_from_event(event)
            if maybe_final:
                final = maybe_final
        if not final:
            run = await _legacy_agent.arun(prompt, session_id=session_id)
            final = _content_to_text(run.content)
        yield ("reasoning", "Agent finished\n")
        yield ("content", final)
        return

    if model == WORKFLOW_MODEL_ID:
        if _workflow is None:
            raise HTTPException(status_code=503, detail="Workflow not ready")
        yield ("reasoning", "Starting visualization workflow\n")
        stream = _workflow.arun(
            prompt,
            session_id=session_id,
            stream=True,
            stream_events=True,
        )
        final = ""
        async for event in stream:
            progress = _high_level_progress(event)
            if progress:
                yield ("reasoning", progress)
            maybe_final = _final_content_from_event(event)
            if maybe_final:
                final = maybe_final
        if not final:
            run = await _workflow.arun(prompt, session_id=session_id)
            final = _content_to_text(getattr(run, "content", run))
        yield ("content", final)
        return

    raise HTTPException(
        status_code=404,
        detail=(
            f"Unknown model {model!r}. "
            f"Use {LEGACY_MODEL_ID!r} or {WORKFLOW_MODEL_ID!r}."
        ),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _mcp_tools, _legacy_agent, _workflow

    if SqliteDb is None:
        raise RuntimeError("Install AgentOS deps: pip install -U 'agno[os]'")

    db_path = Path(__file__).resolve().parent / "tmp" / "librechat_bridge.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDb(db_file=str(db_path))

    _mcp_tools = build_mcp_tools(refresh_connection=True)
    await _mcp_tools.connect()

    _legacy_agent = build_legacy_agent(
        _mcp_tools,
        db=db,
        agent_id=LEGACY_MODEL_ID,
        agent_name="Visualization Agent (LibreChat)",
    )
    _workflow = build_visualization_workflow(db=db, mcp_tools=_mcp_tools)
    # Prefer event streaming when callers request stream=True
    if hasattr(_workflow, "stream_events"):
        _workflow.stream_events = True

    try:
        yield
    finally:
        if _mcp_tools is not None:
            close = getattr(_mcp_tools, "close", None) or getattr(
                _mcp_tools, "disconnect", None
            )
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
        _mcp_tools = None
        _legacy_agent = None
        _workflow = None


app = FastAPI(
    title="Atlys Visualization · LibreChat bridge",
    description=(
        "OpenAI-compatible shim: high-level Agno progress → reasoning_content; "
        "deep traces stay in Langfuse (agno-dev)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *config.AGENTOS_CORS_ORIGINS,
        "http://localhost:3080",
        "http://127.0.0.1:3080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: Any = ""


class ChatCompletionRequest(BaseModel):
    model: str = LEGACY_MODEL_ID
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    user: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def _completion_payload(
    *,
    model: str,
    text: str,
    completion_id: str,
    reasoning: str = "",
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if reasoning:
        message["reasoning_content"] = reasoning
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _sse_chunk(
    *,
    model: str,
    completion_id: str,
    content: str | None = None,
    reasoning: str | None = None,
    finish: str | None = None,
    role: str | None = None,
) -> str:
    delta: dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content:
        delta["content"] = content
    if reasoning:
        delta["reasoning_content"] = reasoning
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "legacy": LEGACY_MODEL_ID,
        "workflow": WORKFLOW_MODEL_ID,
        "progress": "reasoning_content",
    }


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": LEGACY_MODEL_ID,
                "object": "model",
                "created": now,
                "owned_by": "atlys",
            },
            {
                "id": WORKFLOW_MODEL_ID,
                "object": "model",
                "created": now,
                "owned_by": "atlys",
            },
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest) -> Any:
    messages = [m.model_dump() for m in body.messages]
    prompt = _messages_to_prompt(messages)
    session_id = body.user or str(uuid.uuid4())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    if not body.stream:
        reasoning_parts: list[str] = []
        final = ""
        async for channel, text in _iter_model_events(
            body.model, prompt, session_id=session_id
        ):
            if channel == "reasoning":
                reasoning_parts.append(text)
            else:
                final = text
        return _completion_payload(
            model=body.model,
            text=final,
            completion_id=completion_id,
            reasoning="".join(reasoning_parts),
        )

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_chunk(
            model=body.model,
            completion_id=completion_id,
            role="assistant",
        )
        async for channel, text in _iter_model_events(
            body.model, prompt, session_id=session_id
        ):
            if not text:
                continue
            if channel == "reasoning":
                yield _sse_chunk(
                    model=body.model,
                    completion_id=completion_id,
                    reasoning=text,
                )
            else:
                yield _sse_chunk(
                    model=body.model,
                    completion_id=completion_id,
                    content=text,
                )
        yield _sse_chunk(
            model=body.model,
            completion_id=completion_id,
            finish="stop",
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="LibreChat OpenAI-compatible bridge for Visualization Agent",
    )
    parser.add_argument("--host", default=config.AGENTOS_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    import uvicorn

    print(f"LibreChat bridge → http://localhost:{args.port}")
    print(f"OpenAI baseURL   → http://localhost:{args.port}/v1")
    print(f"Models           → {LEGACY_MODEL_ID}, {WORKFLOW_MODEL_ID}")
    print("Progress         → delta.reasoning_content (LibreChat Reasoning panel)")
    print("Deep traces      → Langfuse environment agno-dev")
    print(f"Docs             → http://localhost:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
