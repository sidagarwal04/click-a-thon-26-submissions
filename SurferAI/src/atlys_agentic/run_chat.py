"""FastAPI OpenAI-compatible backend for LibreChat.

Exposes POST /v1/chat/completions wired to CrewAI IngestionFlow (CUJ 1)
and AnalysisFlow (CUJ 2).
"""
from __future__ import annotations

import json
import time
import uuid

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    class StreamingResponse:  # type: ignore
        def __init__(self, generator=None, media_type: str = "text/event-stream"):
            self.generator = generator
            self.media_type = media_type

    class JSONResponse:  # type: ignore
        def __init__(self, content=None, status_code: int = 200):
            self.content = content
            self.status_code = status_code

    class FastAPI:  # type: ignore
        def __init__(self, title: str = ""):
            self.title = title

        def post(self, path: str):
            def decorator(fn):
                return fn
            return decorator

        def get(self, path: str, response_class=None):
            def decorator(fn):
                return fn
            return decorator

    from pydantic import BaseModel, Field

from atlys_agentic import chdb_client, conversational_ingestion, paths, prompts, tools, tracing
from atlys_agentic.flows import analysis_flow, ingestion_flow

app = FastAPI(title="Atlys Agentic Analytics & Ingestion Service (LibreChat Integration)")

# Runtime initialization: Bootstrap chDB schema, base context, and table semantics
try:
    chdb_client.init_schema()
    chdb_client.init_base_context()
    tools.Tool_Bootstrap_Base_Semantics(force=True)
except Exception:
    pass




class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "atlys-instrumentation"
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None

    model_config = {"extra": "allow"}


class IngestionRequest(BaseModel):
    spec_id: str
    table_name: str = ""


class AnalysisRequest(BaseModel):
    question: str
    spec_id: str = "general"
    base_sql: str = "SELECT * FROM purchase_completed"


_DEFAULT_BASE_SQL = "SELECT * FROM purchase_completed"


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/specs")
def list_specs():
    specs = []
    if paths.SPECS_DIR.exists():
        for p in sorted(paths.SPECS_DIR.glob("*")):
            if p.is_dir():
                spec_name = p.name.replace("_", " ").title()
                specs.append({
                    "id": p.name,
                    "name": spec_name,
                    "table_default": p.name.split("_", 1)[-1] if "_" in p.name else p.name,
                })
    return {"specs": specs}


@app.post("/api/ingest/propose")
def propose_ingestion(req: IngestionRequest):
    chdb_client.init_schema()
    chdb_client.init_base_context()
    state = ingestion_flow.generate_proposal(
        spec_id=req.spec_id,
        table_name=req.table_name,
        dry_run=True,
    )
    return {
        "status": "success",
        "spec_id": req.spec_id,
        "table_name": state.table_name or req.table_name,
        "dry_run": True,
        "approved": False,
        "ddl": state.ddl,
        "mv_ddl": state.mv_ddl,
        "diff_result": state.diff_result,
        "strategy": state.strategy,
        "violations": state.violations,
        "proposal_md": state.proposal_md,
        "trace_id": state.trace_id,
        "trace_url": state.trace_url,
    }


@app.post("/api/ingest/approve")
def approve_ingestion(req: IngestionRequest):
    chdb_client.init_schema()
    chdb_client.init_base_context()
    state = ingestion_flow.deploy_approved_proposal(
        spec_id=req.spec_id,
        table_name=req.table_name,
    )
    return {
        "status": "success" if state.approved else "failed",
        "spec_id": req.spec_id,
        "table_name": state.table_name or req.table_name,
        "approved": state.approved,
        "ddl_result": state.ddl_result,
        "diff_result": state.diff_result,
        "load_result": state.load_result,
        "receipt_md": state.receipt_md,
        "artifacts": state.artifacts,
        "trace_id": state.trace_id,
    }


@app.post("/api/analyze/query")
def analyze_query(req: AnalysisRequest):
    chdb_client.init_schema()
    chdb_client.init_base_context()
    result = analysis_flow.run(question=req.question, spec_id=req.spec_id, base_sql=req.base_sql)
    return {
        "status": "success",
        "question": req.question,
        "spec_id": req.spec_id,
        "executive_summary": result.get("executive_summary", ""),
        "answer_md": result.get("answer_md", ""),
        "confidence": result.get("confidence", {}),
        "known_issue_match": result.get("known_issue_match", False),
        "matched_known_issue": result.get("matched_known_issue", ""),
        "cuts": result.get("cuts", {}),
        "views": result.get("views", {}),
        "sql_queries": result.get("sql_queries", []),
        "trace_id": result.get("trace_id", ""),
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    messages_list = [{"role": m.role, "content": m.content} for m in req.messages]
    intent, context_data = conversational_ingestion.detect_chat_intent(messages_list, model=req.model)
    question = req.messages[-1].content
    trace_id = tracing.new_trace("librechat", run_mode="librechat_client")
    is_instrumentation_model = req.model == "atlys-instrumentation"

    with tracing.step(
        "librechat_query_execution",
        input={"question": question, "model": req.model, "intent": intent},
        metadata={"client": "librechat_client", "model": req.model, "intent": intent},
        run_mode="librechat_client",
    ):
        if is_instrumentation_model:
            # CUJ 1: Dedicated Instrumentation Engineer & Orchestrator
            if intent == "GREETING":
                content = conversational_ingestion.INSTRUMENTATION_GREETING_MD
            elif intent == "LIST_PATHS":
                content = conversational_ingestion.format_available_paths_card()
            elif intent == "LIST_SPECS":
                content = conversational_ingestion.format_available_specs_card()
            elif intent == "BATCH_INGEST_PROPOSAL":
                folder = context_data.get("folder_path", "problem statment/specs")
                content = conversational_ingestion.format_batch_proposal_card(folder)
            elif intent == "HITL_APPROVE":
                table_hint = context_data.get("table_hint")
                content = conversational_ingestion.handle_hitl_deployment(
                    table_name=table_hint,
                    spec_id=context_data.get("spec_id"),
                    history=messages_list,
                )
            elif intent == "HITL_REJECT":
                content = conversational_ingestion.handle_hitl_rejection(
                    table_name=context_data.get("table_name"),
                    history=messages_list,
                )
            elif intent == "INGESTION_PROPOSAL":
                spec_id = context_data.get("spec_id", "01_express_checkout")
                table_name = context_data.get("table_name")
                chdb_client.init_schema()
                chdb_client.init_base_context()
                state = ingestion_flow.generate_proposal(
                    spec_id=spec_id,
                    table_name=table_name,
                    dry_run=True,
                )
                content = state.proposal_md
            elif intent == "INGESTION_FOLLOWUP":
                q = context_data.get("question", question)
                tbl = context_data.get("table_name")
                spec = context_data.get("spec_id")
                tr = context_data.get("trace_id")
                content = conversational_ingestion.handle_followup_question(
                    question=q,
                    table_name=tbl,
                    spec_id=spec,
                    trace_id=tr,
                )
            else:
                content = conversational_ingestion.INSTRUMENTATION_SCOPE_NOTICE_MD
        else:
            # CUJ 2: Dedicated Analytics Agent & Orchestrator
            if intent == "GREETING":
                content = prompts.GREETING_RESPONSE_MD
            elif intent == "LIST_PATHS":
                content = conversational_ingestion.format_available_paths_card()
            elif intent == "LIST_SPECS":
                content = conversational_ingestion.format_available_specs_card()
            elif intent in ("INGESTION_PROPOSAL", "BATCH_INGEST_PROPOSAL", "HITL_APPROVE", "INGESTION_FOLLOWUP"):
                content = conversational_ingestion.ANALYST_SCOPE_NOTICE_MD
            else:
                result = analysis_flow.run(question=question, spec_id="chat", base_sql=_DEFAULT_BASE_SQL)
                content = result.get("answer_md", "")



        tracing.span(
            trace_id,
            "chat_completions",
            {"question": question, "model": req.model, "intent": intent},
            {"content": content[:100]},
            metadata={"client": "librechat_client", "intent": intent, "agent": "analytics_agent"},
            run_mode="librechat_client",
        )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # Handle streaming if requested by LibreChat
    if req.stream:
        def sse_generator():
            init_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(init_chunk)}\n\n"

            lines = content.splitlines(keepends=True)
            for chunk_str in lines:
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk_str},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


def start_service(host: str = "0.0.0.0", port: int = 8008):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
