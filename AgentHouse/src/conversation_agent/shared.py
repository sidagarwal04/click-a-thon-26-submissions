"""Shared helpers for the Visualization Agent workflow (not the unused _old agent)."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from conversation_agent import config

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

_DIR = Path(__file__).resolve().parent
_langfuse_ready = False
MCP_RUN_QUERY_TOOL = "run_query"

# Workflow step ids — also used as Langfuse tags (step:<name>)
WORKFLOW_STEP_NAMES = (
    "discover_schema",
    "pack_for_plan_visualization",
    "plan_visualization",
    "run_analytics",
    "generate_query",
    "execute",
    "context_agent",
)


def langfuse_base_tags(*, step: str | None = None) -> list[str]:
    """Tags for Langfuse filters: environment + optional workflow step."""
    labels = model_trace_labels()
    environment = config.LANGFUSE_TRACING_ENVIRONMENT or "agno-dev"
    tags = [
        environment,
        "agno",
        labels["model_provider"],
        labels["model_id"],
        labels["model"],
    ]
    if step:
        tags.extend([step, f"step:{step}"])
    return tags


def detect_workflow_step_from_span(span: Any) -> str | None:
    """Best-effort step name from OTEL span name/attributes."""
    attrs = getattr(span, "attributes", None) or {}
    blobs: list[str] = [str(getattr(span, "name", "") or "")]
    for key, value in attrs.items():
        blobs.append(f"{key}={value}")
        if isinstance(value, str):
            blobs.append(value)
        elif isinstance(value, (list, tuple)):
            blobs.extend(str(v) for v in value)
    haystack = " ".join(blobs).lower().replace("-", "_")
    for step in WORKFLOW_STEP_NAMES:
        if step in haystack or f"step:{step}" in haystack:
            return step
    if "legacy" in haystack:
        return "legacy"
    return None


def agent_trace_metadata(*, step: str) -> dict[str, str]:
    labels = model_trace_labels()
    return {
        "model_provider": labels["model_provider"],
        "model_id": labels["model_id"],
        "model": labels["model"],
        "step": step,
        "langfuse_environment": config.LANGFUSE_TRACING_ENVIRONMENT or "agno-dev",
    }


def resolve_path(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (_DIR / p)


def load_text_file(path: str, *, label: str) -> str:
    """Load a context/skill file; raise if missing so misconfig is obvious."""
    file_path = resolve_path(path)
    if not file_path.is_file():
        raise RuntimeError(
            f"Missing {label} at {file_path}. "
            f"Set the path in conversation_agent/config.py or provide the file."
        )
    return file_path.read_text(encoding="utf-8")


def build_model() -> Any:
    provider = config.MODEL_PROVIDER.strip().lower()
    if provider in ("claude", "anthropic"):
        from agno.models.anthropic import Claude

        if config.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = config.ANTHROPIC_API_KEY
        elif not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY in conversation_agent/config.py")
        return Claude(
            id=config.MODEL_ID,
            api_key=config.ANTHROPIC_API_KEY or None,
        )

    if provider == "gemini":
        from agno.models.google import Gemini

        api_key = config.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY") or ""
        if not api_key:
            raise RuntimeError("Set GOOGLE_API_KEY in repo-root .env")
        os.environ["GOOGLE_API_KEY"] = api_key

        # New AI Studio auth keys (AQ.*) fail on the default Generative Language
        # client unless Vertex Express mode is used (vertexai=True + api_key).
        use_vertex = bool(config.GOOGLE_GENAI_USE_VERTEXAI) or api_key.startswith("AQ.")
        if use_vertex:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
            client_params: dict[str, Any] = {"api_key": api_key}
            kwargs: dict[str, Any] = {
                "id": config.MODEL_ID,
                "api_key": api_key,
                "vertexai": True,
                "client_params": client_params,
            }
            if config.GOOGLE_CLOUD_PROJECT:
                kwargs["project_id"] = config.GOOGLE_CLOUD_PROJECT
                os.environ["GOOGLE_CLOUD_PROJECT"] = config.GOOGLE_CLOUD_PROJECT
            if config.GOOGLE_CLOUD_LOCATION:
                kwargs["location"] = config.GOOGLE_CLOUD_LOCATION
                os.environ["GOOGLE_CLOUD_LOCATION"] = config.GOOGLE_CLOUD_LOCATION
            return Gemini(**kwargs)

        return Gemini(id=config.MODEL_ID, api_key=api_key)

    if provider == "openai":
        from agno.models.openai import OpenAIChat

        if config.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = config.OPENAI_API_KEY
        elif not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY in conversation_agent/config.py")
        return OpenAIChat(id=config.MODEL_ID)

    raise RuntimeError(
        f"Unknown MODEL_PROVIDER={config.MODEL_PROVIDER!r}; "
        "use 'claude', 'gemini', or 'openai'"
    )


def model_trace_labels() -> dict[str, str]:
    provider = config.MODEL_PROVIDER.strip().lower()
    if provider == "anthropic":
        provider = "claude"
    model_id = config.MODEL_ID
    return {
        "model_provider": provider,
        "model_id": model_id,
        "model": f"{provider}:{model_id}",
    }


DEFAULT_LANGFUSE_SERVICE_NAME = "clickathon-visualization-agent"


def setup_langfuse(*, service_name: str = DEFAULT_LANGFUSE_SERVICE_NAME) -> None:
    """Instrument Agno → OpenTelemetry → Langfuse (idempotent).

    ``service_name`` becomes the OTEL/Langfuse service name so Context vs
    Conversation CLI runs are filterable. First successful call in a process wins.
    """
    global _langfuse_ready
    if _langfuse_ready or not getattr(config, "LANGFUSE_ENABLED", True):
        return
    if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
        raise RuntimeError(
            "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in conversation_agent/config.py"
        )

    from openinference.instrumentation.agno import AgnoInstrumentor
    from opentelemetry import trace as trace_api
    from opentelemetry.context import Context
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    labels = model_trace_labels()
    environment = config.LANGFUSE_TRACING_ENVIRONMENT or "agno-dev"
    resolved_service = (service_name or DEFAULT_LANGFUSE_SERVICE_NAME).strip()
    llm_system = {
        "claude": "anthropic",
        "gemini": "google",
        "openai": "openai",
    }.get(labels["model_provider"], labels["model_provider"])

    class ModelMetadataSpanProcessor(SpanProcessor):
        def on_start(self, span: Span, parent_context: Context | None = None) -> None:
            # First-class Langfuse environment (filterable in UI)
            span.set_attribute("langfuse.environment", environment)
            span.set_attribute("deployment.environment", environment)
            span.set_attribute("deployment.environment.name", environment)
            span.set_attribute("langfuse.trace.metadata.service", resolved_service)
            span.set_attribute(
                "langfuse.observation.metadata.service", resolved_service
            )
            span.set_attribute("langfuse.trace.metadata.model_provider", labels["model_provider"])
            span.set_attribute("langfuse.trace.metadata.model_id", labels["model_id"])
            span.set_attribute("langfuse.trace.metadata.model", labels["model"])
            span.set_attribute(
                "langfuse.observation.metadata.model_provider", labels["model_provider"]
            )
            span.set_attribute(
                "langfuse.observation.metadata.model_id", labels["model_id"]
            )
            span.set_attribute("langfuse.observation.metadata.model", labels["model"])
            span.set_attribute("langfuse.observation.model.name", labels["model_id"])
            span.set_attribute("llm.model_name", labels["model_id"])
            span.set_attribute("llm.system", llm_system)
            step = detect_workflow_step_from_span(span)
            if step:
                span.set_attribute("langfuse.observation.metadata.step", step)
                span.set_attribute("langfuse.trace.metadata.step", step)
            tags = langfuse_base_tags(step=step)
            tags.append(resolved_service)
            span.set_attribute("langfuse.trace.tags", tags)

        def on_end(self, span: ReadableSpan) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    os.environ["LANGFUSE_PUBLIC_KEY"] = config.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = config.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = config.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_BASE_URL"] = config.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = environment
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = (
        f"langfuse.environment={environment},service.name={resolved_service}"
    )

    auth = base64.b64encode(
        f"{config.LANGFUSE_PUBLIC_KEY}:{config.LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    base = config.LANGFUSE_BASE_URL.rstrip("/")
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{base}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

    from opentelemetry.sdk.resources import Resource

    tracer_provider = TracerProvider(
        resource=Resource.create(
            {
                "langfuse.environment": environment,
                "deployment.environment": environment,
                "deployment.environment.name": environment,
                "service.name": resolved_service,
            }
        )
    )
    tracer_provider.add_span_processor(ModelMetadataSpanProcessor())
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    trace_api.set_tracer_provider(tracer_provider=tracer_provider)
    AgnoInstrumentor().instrument()
    _langfuse_ready = True


def clickhouse_mcp_env() -> dict[str, str]:
    if not config.CLICKHOUSE_HOST or not config.CLICKHOUSE_USER:
        raise RuntimeError(
            "Set CLICKHOUSE_HOST and CLICKHOUSE_USER in conversation_agent/config.py"
        )
    env = {
        "CLICKHOUSE_HOST": config.CLICKHOUSE_HOST,
        "CLICKHOUSE_PORT": str(config.CLICKHOUSE_PORT),
        "CLICKHOUSE_USER": config.CLICKHOUSE_USER,
        "CLICKHOUSE_PASSWORD": config.CLICKHOUSE_PASSWORD,
        "CLICKHOUSE_SECURE": "true" if config.CLICKHOUSE_SECURE else "false",
        "CLICKHOUSE_VERIFY": "true" if config.CLICKHOUSE_VERIFY else "false",
        "CLICKHOUSE_CONNECT_TIMEOUT": str(config.CLICKHOUSE_CONNECT_TIMEOUT),
        "CLICKHOUSE_SEND_RECEIVE_TIMEOUT": str(config.CLICKHOUSE_SEND_RECEIVE_TIMEOUT),
    }
    if path := os.environ.get("PATH"):
        env["PATH"] = path
    return env


def build_mcp_tools(
    *,
    refresh_connection: bool = False,
    include_tools: list[str] | None = None,
) -> MCPTools:
    from agno.tools.mcp import MCPTools

    kwargs: dict[str, Any] = {
        "command": config.CLICKHOUSE_MCP_COMMAND,
        "env": clickhouse_mcp_env(),
        "timeout_seconds": config.CLICKHOUSE_MCP_TIMEOUT_SECONDS,
        "refresh_connection": refresh_connection,
    }
    if include_tools is not None:
        kwargs["include_tools"] = include_tools
    return MCPTools(**kwargs)


def _parse_mcp_query_payload(raw: str) -> tuple[list[str], list[list[Any]]]:
    data = json.loads(raw)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(str(data.get("message") or data))
    if not isinstance(data, dict) or "columns" not in data or "rows" not in data:
        raise RuntimeError(f"Unexpected MCP run_query payload: {raw[:500]}")
    columns = list(data["columns"])
    rows = [list(row) for row in data["rows"]]
    return columns, rows


async def run_query_via_mcp(
    sql: str,
    *,
    mcp_tools: Optional[MCPTools] = None,
) -> tuple[list[str], list[list[Any]]]:
    """Execute one query via ClickHouse MCP `run_query`; return (columns, rows)."""

    async def _call(mcp: MCPTools) -> tuple[list[str], list[list[Any]]]:
        if not getattr(mcp, "_initialized", False):
            await mcp.connect()
        if mcp.session is None:
            raise RuntimeError("ClickHouse MCP session is not connected")

        result = await mcp.session.call_tool(MCP_RUN_QUERY_TOOL, {"query": sql})
        if result.isError:
            raise RuntimeError(f"MCP {MCP_RUN_QUERY_TOOL} error: {result.content}")

        chunks: list[str] = []
        for item in result.content or []:
            text = getattr(item, "text", None)
            if text:
                chunks.append(text)
        raw = "\n".join(chunks).strip()
        if not raw:
            raise RuntimeError(f"MCP {MCP_RUN_QUERY_TOOL} returned empty content")
        return _parse_mcp_query_payload(raw)

    if mcp_tools is not None:
        return await _call(mcp_tools)

    async with build_mcp_tools() as mcp:
        return await _call(mcp)
