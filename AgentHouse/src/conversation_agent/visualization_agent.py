"""Visualization Agent workflow: schema → VizPlan → multi run_analytics.

Modes:
    CLI (default):  one-shot prompt → print MultiExecuteResult JSON
    AgentOS:        FastAPI surface (connect via os.agno.com)

Analytics: template SQL + clickhouse-connect; fallback LLM generate_query + MCP.
Plan step may emit 1–5 VizSpecs; each is executed and merged.

Run (CLI):
    python -m conversation_agent.visualization_agent
    python -m conversation_agent.visualization_agent "OTP success by device last 30 days"

Run (AgentOS):
    python -m conversation_agent.visualization_agent --os
    python -m conversation_agent.visualization_agent --os --port 7777
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from agno.tools.mcp import MCPTools
from agno.workflow import Step, Workflow
from pydantic import BaseModel

from conversation_agent import config
from conversation_agent.shared import (
    DEFAULT_LANGFUSE_SERVICE_NAME,
    build_mcp_tools,
    setup_langfuse,
)
from conversation_agent.steps import (
    discover_schema,
    plan_visualization,
    run_analytics,
)
from conversation_agent.steps.glue import pack_for_plan_visualization

try:
    from agno.db.sqlite import SqliteDb
    from agno.os import AgentOS
except ImportError:  # CLI-only install without agno[os]
    SqliteDb = None  # type: ignore[assignment,misc]
    AgentOS = None  # type: ignore[assignment,misc]


def build_visualization_workflow(
    *,
    db: Any = None,
    mcp_tools: MCPTools | None = None,
) -> Workflow:
    """Assemble the Visualization Agent workflow (schema → plan → analytics)."""
    setup_langfuse(service_name=DEFAULT_LANGFUSE_SERVICE_NAME)
    return Workflow(
        id=config.WORKFLOW_ID,
        name=config.AGENT_NAME,
        description=config.AGENTOS_DESCRIPTION,
        db=db,
        steps=[
            discover_schema.build_step(db=db),
            Step(
                name="pack_for_plan_visualization",
                description="Pack user question + schema for viz planner",
                executor=pack_for_plan_visualization,
            ),
            plan_visualization.build_step(db=db),
            run_analytics.build_step(mcp_tools=mcp_tools),
        ],
    )


def _content_to_dict(content: Any) -> dict[str, Any]:
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
            return {"content": parsed}
        except json.JSONDecodeError:
            return {"content": content}
    raise TypeError(f"Unexpected workflow content type: {type(content)}")


async def run_visualization_workflow(prompt: str) -> dict[str, Any]:
    """CLI path: prefer direct CH analytics; attach MCP when available for fallback."""
    try:
        async with build_mcp_tools() as mcp_tools:
            workflow = build_visualization_workflow(mcp_tools=mcp_tools)
            run = await workflow.arun(prompt)
            return _content_to_dict(run.content)
    except Exception as mcp_exc:  # noqa: BLE001
        print(f"[CLI] MCP unavailable ({mcp_exc}); running without MCP fallback")
        workflow = build_visualization_workflow(mcp_tools=None)
        run = await workflow.arun(prompt)
        return _content_to_dict(run.content)


# ---------------------------------------------------------------------------
# AgentOS surface
# ---------------------------------------------------------------------------

agent_os: Any = None
app: Any = None
visualization_workflow: Any = None
visualization_agent_legacy: Any = None
_agent_os_init_error: Exception | None = None

LEGACY_AGENT_ID = "visualization-agent-legacy"
LEGACY_AGENT_NAME = "Visualization Agent (legacy)"


def bootstrap_agent_os() -> None:
    """Build AgentOS with workflow (+ optional legacy MCP agent)."""
    global agent_os, app, visualization_workflow, visualization_agent_legacy
    global _agent_os_init_error

    if app is not None:
        return
    if AgentOS is None or SqliteDb is None:
        raise RuntimeError(
            "AgentOS not available. Install with: uv add 'agno[os]'   "
            "(or: uv pip install 'agno[os]')"
        )

    try:
        db_path = Path(__file__).resolve().parent / config.AGENTOS_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os_db = SqliteDb(db_file=str(db_path))

        os_mcp_tools = None
        agents: list[Any] = []
        try:
            from conversation_agent.visualization_agent_old import (
                build_agent as build_legacy_agent,
            )

            # Full MCP toolset for legacy agent; execute step uses run_query
            os_mcp_tools = build_mcp_tools(refresh_connection=True)
            visualization_agent_legacy = build_legacy_agent(
                os_mcp_tools,
                db=os_db,
                agent_id=LEGACY_AGENT_ID,
                agent_name=LEGACY_AGENT_NAME,
            )
            agents.append(visualization_agent_legacy)
        except Exception as mcp_exc:  # noqa: BLE001
            print(f"[AgentOS] legacy MCP agent skipped: {mcp_exc}")
            visualization_agent_legacy = None

        visualization_workflow = build_visualization_workflow(
            db=os_db,
            mcp_tools=os_mcp_tools,
        )
        agent_os = AgentOS(
            id=config.AGENTOS_ID,
            description=config.AGENTOS_DESCRIPTION,
            agents=agents,
            workflows=[visualization_workflow],
            db=os_db,
            cors_allowed_origins=list(config.AGENTOS_CORS_ORIGINS),
        )
        app = agent_os.get_app()
        _agent_os_init_error = None
    except Exception as exc:  # noqa: BLE001
        _agent_os_init_error = exc
        raise


def _should_bootstrap_agent_os_on_import() -> bool:
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
        f"Workflow → id={config.WORKFLOW_ID}  name={config.AGENT_NAME!r}"
    )
    print(
        f"Agent    → id={LEGACY_AGENT_ID}  name={LEGACY_AGENT_NAME!r} "
        f"(POST /agents/{LEGACY_AGENT_ID}/runs)"
    )
    agent_os.serve(
        app="conversation_agent.visualization_agent:app",
        host=config.AGENTOS_HOST,
        port=bind_port,
        reload=False,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Visualization Agent workflow (CLI or AgentOS)",
    )
    parser.add_argument(
        "--os",
        "--serve",
        dest="serve_os",
        action="store_true",
        help="Surface the workflow via Agno AgentOS (FastAPI on --port)",
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
        result = asyncio.run(run_visualization_workflow(prompt))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
