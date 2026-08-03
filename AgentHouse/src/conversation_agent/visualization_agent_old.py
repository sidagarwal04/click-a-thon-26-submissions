"""UNUSED — kept as reference. Active entrypoint is visualization_agent.py (Workflow).

Visualization agent: natural language → ClickHouse MCP query → AnalyticsResponse JSON.

Modes:
    CLI (default):  one-shot prompt → print AnalyticsResponse JSON
    AgentOS:        FastAPI surface (connect via os.agno.com)

Install:
    pip install -U 'agno[os]' anthropic pydantic
    pip install -U openinference-instrumentation-agno opentelemetry-sdk opentelemetry-exporter-otlp
    # google-genai / openai optional for other MODEL_PROVIDER values
    # also need: mcp-clickhouse (pip)

Config:
    Edit conversation_agent/config.py (ClickHouse, model, Langfuse, AgentOS).

Run (CLI):
    python -m conversation_agent.visualization_agent
    python -m conversation_agent.visualization_agent "OTP success by device last 30 days"

Run (AgentOS):
    python -m conversation_agent.visualization_agent --os
    python -m conversation_agent.visualization_agent --os --port 7777
    # API docs: http://localhost:7777/docs
    # UI:       https://os.agno.com → Connect OS → http://localhost:7777
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal, Optional, Union

from agno.agent import Agent
from agno.tools.mcp import MCPTools
from pydantic import BaseModel, Field

from conversation_agent import config

_DIR = Path(__file__).resolve().parent
DATASETS_MD = _DIR / "clickhouse_datasets.md"
_langfuse_ready = False

try:
    from agno.db.sqlite import SqliteDb
    from agno.os import AgentOS
except ImportError:  # CLI-only install without agno[os]
    SqliteDb = None  # type: ignore[assignment,misc]
    AgentOS = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Structured output (frontend contract)
# ---------------------------------------------------------------------------


class AnalyticsPoint(BaseModel):
    fromTime: str = Field(..., description="ISO-8601 window start (inclusive)")
    toTime: str = Field(..., description="ISO-8601 window end (exclusive or inclusive)")
    metricName: str = Field(..., description="Metric key, e.g. conversion_rate, otp_success")
    metricValue: float = Field(..., description="Numeric metric value for this point")
    dimensionName: Optional[str] = Field(
        None,
        description='Optional slice key, e.g. "country" / "device_type". Null = undimensioned.',
    )
    dimensionValue: Optional[str] = Field(
        None,
        description='Optional slice value, e.g. "IN" / "iOS". Null = undimensioned.',
    )


class InsightData(BaseModel):
    metricNames: list[str] = Field(
        ...,
        description="Metric names present in points (may be one or more series)",
    )
    points: list[AnalyticsPoint] = Field(
        default_factory=list,
        description="Aggregated points only — never raw event rows",
    )


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(..., description="Narrative / caveat / SQL summary for the UI")


class InsightBlock(BaseModel):
    type: Literal["insight"] = "insight"
    title: Optional[str] = Field(None, description="Short chart / insight title")
    caption: Optional[str] = Field(None, description="Supporting sentence under the title")
    kind: Literal["timeseries", "breakdown", "comparison", "table", "funnel"] = Field(
        ...,
        description="Chart kind: timeseries | breakdown | comparison | table | funnel",
    )
    data: InsightData


AnalyticsBlock = Union[TextBlock, InsightBlock]


class AnalyticsResponse(BaseModel):
    """Frontend analytics payload — ordered blocks of text and/or insights."""

    blocks: list[AnalyticsBlock] = Field(
        ...,
        description="Ordered UI blocks; any mix of text and insight",
    )


# ---------------------------------------------------------------------------
# ClickHouse MCP
# ---------------------------------------------------------------------------


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


def build_mcp_tools(*, refresh_connection: bool = False) -> MCPTools:
    return MCPTools(
        command=config.CLICKHOUSE_MCP_COMMAND,
        env=clickhouse_mcp_env(),
        timeout_seconds=config.CLICKHOUSE_MCP_TIMEOUT_SECONDS,
        refresh_connection=refresh_connection,
    )


INSTRUCTIONS = [
    "You turn a natural-language analytics question into ClickHouse queries via MCP, "
    "then return ONLY an AnalyticsResponse JSON object matching the frontend contract.",
    "Use the ClickHouse dataset catalog below as ground truth for databases, tables, "
    "columns, funnel order, and time window. Prefer querying those tables directly "
    "instead of rediscovering schema from scratch; only call list_tables / list_databases "
    "when the catalog is insufficient.",
    "Workflow: (1) pick tables/columns from the catalog, "
    "(2) write aggregate SELECTs (uniq, group by, windowFunnel — never SELECT * raw events), "
    "(3) run_select_query, "
    "(4) map rows into blocks.",
    "blocks is an ordered list. Typical shape: "
    "optional text (takeaway / SQL / caveats) then one or more insight blocks.",
    "insight.kind: timeseries (over time), breakdown (one metric by dimension), "
    "comparison (side-by-side metrics or segments), table, funnel.",
    "Each AnalyticsPoint needs fromTime, toTime, metricName, metricValue. "
    "Set dimensionName + dimensionValue together for sliced series; omit/null both if undimensioned.",
    "insight.data.metricNames must list every metricName used in points.",
    "Prefer cuts by device_type, geoip_country_code, destination when relevant.",
    "All metricValues must come from query results — do not invent numbers.",
    "On empty/failed queries: still return valid AnalyticsResponse with a text block explaining "
    "the failure and an insight block with empty points if useful.",
]


def load_datasets_context() -> str:
    """Load clickhouse_datasets.md into the system prompt."""
    if not DATASETS_MD.is_file():
        return (
            f"Default database: {config.CLICKHOUSE_DATABASE}. "
            f"(Missing dataset catalog at {DATASETS_MD.name}.)"
        )
    return (
        "ClickHouse dataset catalog (use this context when querying via MCP):\n\n"
        + DATASETS_MD.read_text(encoding="utf-8")
    )


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

        if config.GOOGLE_API_KEY:
            os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY
        elif not os.environ.get("GOOGLE_API_KEY"):
            raise RuntimeError("Set GOOGLE_API_KEY in conversation_agent/config.py")
        return Gemini(id=config.MODEL_ID, api_key=config.GOOGLE_API_KEY or None)

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
    """Stable labels for comparing models in Langfuse."""
    provider = config.MODEL_PROVIDER.strip().lower()
    # Normalize aliases so filters stay consistent across runs
    if provider == "anthropic":
        provider = "claude"
    model_id = config.MODEL_ID
    return {
        "model_provider": provider,
        "model_id": model_id,
        "model": f"{provider}:{model_id}",
    }


def setup_langfuse() -> None:
    """Instrument Agno → OpenTelemetry → Langfuse (idempotent)."""
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
    environment = getattr(config, "LANGFUSE_TRACING_ENVIRONMENT", None) or "agno-dev"
    llm_system = {
        "claude": "anthropic",
        "gemini": "google",
        "openai": "openai",
    }.get(labels["model_provider"], labels["model_provider"])

    class ModelMetadataSpanProcessor(SpanProcessor):
        """Stamp environment + model labels on every span for Langfuse filters."""

        def on_start(self, span: Span, parent_context: Context | None = None) -> None:
            span.set_attribute("langfuse.environment", environment)
            span.set_attribute("deployment.environment", environment)
            span.set_attribute("deployment.environment.name", environment)
            span.set_attribute("langfuse.trace.metadata.model_provider", labels["model_provider"])
            span.set_attribute("langfuse.trace.metadata.model_id", labels["model_id"])
            span.set_attribute("langfuse.trace.metadata.model", labels["model"])
            span.set_attribute(
                "langfuse.observation.metadata.model_provider", labels["model_provider"]
            )
            span.set_attribute(
                "langfuse.observation.metadata.model_id", labels["model_id"]
            )
            span.set_attribute(
                "langfuse.observation.metadata.model", labels["model"]
            )
            span.set_attribute("langfuse.observation.model.name", labels["model_id"])
            span.set_attribute("llm.model_name", labels["model_id"])
            span.set_attribute("llm.system", llm_system)
            step = None
            # Best-effort: parse step from span name / attributes (mirrors shared.py)
            blobs = [str(getattr(span, "name", "") or "")]
            for key, value in (getattr(span, "attributes", None) or {}).items():
                blobs.append(f"{key}={value}")
            hay = " ".join(blobs).lower().replace("-", "_")
            for candidate in (
                "discover_schema",
                "pack_for_plan_visualization",
                "plan_visualization",
                "generate_query",
                "execute",
                "legacy",
            ):
                if candidate in hay:
                    step = candidate
                    break
            tags = [
                environment,
                "agno",
                labels["model_provider"],
                labels["model_id"],
                labels["model"],
            ]
            if step:
                tags.extend([step, f"step:{step}"])
                span.set_attribute("langfuse.observation.metadata.step", step)
                span.set_attribute("langfuse.trace.metadata.step", step)
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
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"langfuse.environment={environment}"

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
                "service.name": "clickathon-visualization-agent-legacy",
            }
        )
    )
    tracer_provider.add_span_processor(ModelMetadataSpanProcessor())
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    trace_api.set_tracer_provider(tracer_provider=tracer_provider)
    AgnoInstrumentor().instrument()
    _langfuse_ready = True


def build_agent(
    mcp_tools: MCPTools,
    *,
    db: Any = None,
    agent_id: str | None = None,
    agent_name: str | None = None,
) -> Agent:
    setup_langfuse()
    labels = model_trace_labels()
    return Agent(
        id=agent_id or config.AGENT_ID,
        name=agent_name or config.AGENT_NAME,
        model=build_model(),
        tools=[mcp_tools],
        db=db,
        instructions=[*INSTRUCTIONS, load_datasets_context()],
        output_schema=AnalyticsResponse,
        use_json_mode=True,  # tools + structured output
        markdown=False,
        add_history_to_context=bool(db),
        num_history_runs=config.AGENT_HISTORY_RUNS if db else 0,
        metadata={
            "model_provider": labels["model_provider"],
            "model_id": labels["model_id"],
            "model": labels["model"],
            "step": "legacy",
            "langfuse_environment": getattr(
                config, "LANGFUSE_TRACING_ENVIRONMENT", None
            )
            or "agno-dev",
        },
    )


def _content_to_dict(content: Any) -> dict[str, Any]:
    if isinstance(content, AnalyticsResponse):
        return content.model_dump(mode="json")
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return json.loads(content)
    raise TypeError(f"Unexpected agent content type: {type(content)}")


async def run_visualization_agent(prompt: str) -> dict[str, Any]:
    """One-shot CLI path: connect MCP, run once, disconnect."""
    async with build_mcp_tools() as mcp_tools:
        agent = build_agent(mcp_tools)
        run = await agent.arun(prompt)
    return _content_to_dict(run.content)


# ---------------------------------------------------------------------------
# AgentOS surface (module-level `app` for uvicorn)
# AgentOS owns MCPTools lifespan — do not use reload=True with MCP.
# ---------------------------------------------------------------------------

agent_os: Any = None
app: Any = None
visualization_agent: Any = None
_agent_os_init_error: Exception | None = None


def bootstrap_agent_os() -> None:
    """Build AgentOS + module-level `app` (idempotent)."""
    global agent_os, app, visualization_agent, _agent_os_init_error

    if app is not None:
        return
    if AgentOS is None or SqliteDb is None:
        raise RuntimeError(
            "AgentOS not available. Install with: pip install -U 'agno[os]'"
        )

    try:
        from pathlib import Path

        db_path = Path(__file__).resolve().parent / config.AGENTOS_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os_db = SqliteDb(db_file=str(db_path))
        # refresh_connection helps stdio mcp-clickhouse survive across runs
        os_mcp_tools = build_mcp_tools(refresh_connection=True)
        visualization_agent = build_agent(os_mcp_tools, db=os_db)
        agent_os = AgentOS(
            id=config.AGENTOS_ID,
            description=config.AGENTOS_DESCRIPTION,
            agents=[visualization_agent],
            db=os_db,
            cors_allowed_origins=list(config.AGENTOS_CORS_ORIGINS),
        )
        app = agent_os.get_app()
        _agent_os_init_error = None
    except Exception as exc:  # noqa: BLE001 — surface later on --os
        _agent_os_init_error = exc
        raise


def _should_bootstrap_agent_os_on_import() -> bool:
    """True when uvicorn (or explicit flag) is loading this module for AgentOS."""
    if os.getenv("AGENTOS_BOOTSTRAP") == "1":
        return True
    argv = " ".join(sys.argv).lower()
    return "uvicorn" in argv or "agentos" in argv


if AgentOS is not None and _should_bootstrap_agent_os_on_import():
    try:
        bootstrap_agent_os()
    except Exception as exc:  # noqa: BLE001
        _agent_os_init_error = exc


def serve_agent_os(port: int | None = None) -> None:
    os.environ["AGENTOS_BOOTSTRAP"] = "1"
    try:
        bootstrap_agent_os()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Failed to start AgentOS: {exc}") from exc

    assert agent_os is not None
    bind_port = port if port is not None else config.AGENTOS_PORT
    print(f"AgentOS → http://localhost:{bind_port}")
    print(f"API docs → http://localhost:{bind_port}/docs")
    print("UI       → https://os.agno.com  (Connect OS → local endpoint above)")
    print(
        f"Run API  → POST /agents/{config.AGENT_ID}/runs "
        "(form: message=..., stream=false)"
    )
    # Do not use reload=True — it breaks MCPTools lifespan.
    agent_os.serve(
        app="conversation_agent.visualization_agent:app",
        host=config.AGENTOS_HOST,
        port=bind_port,
        reload=False,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Visualization agent (CLI or AgentOS)",
    )
    parser.add_argument(
        "--os",
        "--serve",
        dest="serve_os",
        action="store_true",
        help="Surface the agent via Agno AgentOS (FastAPI on --port)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"AgentOS port (default from config: {config.AGENTOS_PORT})",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Natural-language question (CLI mode only)",
    )
    args = parser.parse_args(argv)

    if args.serve_os:
        serve_agent_os(port=args.port)
        return

    prompt = " ".join(args.prompt).strip() or config.DEFAULT_PROMPT
    try:
        result = asyncio.run(run_visualization_agent(prompt))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
