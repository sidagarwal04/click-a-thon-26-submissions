"""FastAPI app — mounts MCP (SSE) + REST routes (ENGINEERING.md §4.2 `app.py`).

One FastAPI service = MCP server + event-loop host + thin REST API (D7).
Startup: ensure meta.* tables + atlys.event_log exist, seed the context layer,
create the flagship MV. Everything is deterministic-first: with no Langfuse
keys we use the NullTracer; with no ClickHouse we can run in dry-run mode.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import api
from .agents.analytics import AnalyticsAgent
from .agents.context import ContextAgent
from .agents.instrumentation import InstrumentationAgent
from .agents.mv import create_mv_funnel_daily
from .bus import EventBus
from .settings import Settings
from .store import ClickHouseStore, DryRunStore
from .tracing import make_tracer

log = logging.getLogger("atlys.app")

# Bootstrap DDL for the operational tables (meta.* §3.3 + atlys.event_log §2.4).
# `meta` is its own database (mirrors how the doc names meta.* tables).
DDL_STATEMENTS = [
    "CREATE DATABASE IF NOT EXISTS meta",

    """CREATE TABLE IF NOT EXISTS meta.schema_catalog (
        table_name String, ddl String, rationale String, source_spec String,
        event_order String, columns String, row_count UInt64, trace_id String,
        created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY (table_name, created_at)""",
    """CREATE TABLE IF NOT EXISTS meta.schema_changelog (
        version UInt64, agent LowCardinality(String),
        action LowCardinality(String), object String, diff String, rationale String,
        trace_id String, created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY (version, object)""",
    """CREATE TABLE IF NOT EXISTS meta.context_snapshots (
        version UInt64, content String, content_hash String,
        diff_from_prev String, trace_id String, created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY version""",
    """CREATE TABLE IF NOT EXISTS meta.context_changelog (
        version UInt64, agent LowCardinality(String),
        action LowCardinality(String), object String, diff String, rationale String,
        trace_id String, created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY (version, created_at)""",
    """CREATE TABLE IF NOT EXISTS meta.insights (
        spec String, title String, summary String, confidence String,
        evidence String, trace_id String, created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY (created_at)""",
    """CREATE TABLE IF NOT EXISTS meta.known_issues (
        issue_id String, title String, evidence String, status String,
        updated_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY issue_id""",
    """CREATE TABLE IF NOT EXISTS meta.pending_runs (
        run_id String, state LowCardinality(String), spec_dir String,
        schema_card String, trace_id String, runner_token String DEFAULT '',
        created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree ORDER BY run_id
    TTL created_at + INTERVAL 180 DAY""",
    # Existing deployments created pending_runs without runner_token — add it.
    "ALTER TABLE meta.pending_runs ADD COLUMN IF NOT EXISTS runner_token String DEFAULT ''",
    # Existing deployments created pending_runs without the TTL — apply retroactively.
    "ALTER TABLE meta.pending_runs MODIFY TTL created_at + INTERVAL 180 DAY",
    """CREATE TABLE IF NOT EXISTS meta.migration_journal (
        migration_id String,
        table_name String,
        action LowCardinality(String),
        plan_hash String,
        status LowCardinality(String),
        run_id String,
        trace_id String,
        error String,
        created_at DateTime DEFAULT now(),
        applied_at Nullable(DateTime)
    ) ENGINE = MergeTree ORDER BY (table_name, migration_id, created_at)""",
    """CREATE TABLE IF NOT EXISTS atlys.event_log (
        event_id String, event_type LowCardinality(String), aggregate_id String,
        version UInt64, actor LowCardinality(String), payload String,
        trace_id String, created_at DateTime64(3)
    ) ENGINE = MergeTree ORDER BY (event_type, created_at)
    TTL created_at + INTERVAL 90 DAY""",
    # Existing deployments created event_log without the TTL — apply retroactively.
    "ALTER TABLE atlys.event_log MODIFY TTL created_at + INTERVAL 90 DAY",
]


@dataclass
class AppState:
    settings: Settings
    store: object
    tracer: object
    bus: EventBus
    instrumentation: InstrumentationAgent
    context: ContextAgent
    analytics: AnalyticsAgent


app_state: AppState | None = None


def build_store(settings: Settings) -> object:
    """ClickHouseStore when configured; DryRunStore when not (deterministic-first)."""
    if settings.dry_run or not settings.ch_host:
        log.warning("no CH_HOST configured or dry-run set — using in-memory DryRunStore")
        return DryRunStore(database=settings.atlys_db)
    return ClickHouseStore(
        host=settings.ch_host, user=settings.ch_user, password=settings.ch_password,
        secure=settings.ch_secure, database=settings.atlys_db,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    global app_state
    settings = settings or Settings()
    store = build_store(settings)
    tracer = make_tracer(settings.langfuse_pk, settings.langfuse_sk, settings.langfuse_base_url)

    bus = EventBus(store=store, tracer=tracer, max_events_per_run=settings.max_events_per_run)
    instrumentation = InstrumentationAgent(store, bus, settings, tracer)
    context = ContextAgent(store, bus, settings, tracer)
    analytics = AnalyticsAgent(store, bus, settings, tracer)

    bus.register_many({
        "spec.run.requested": [instrumentation.on_run_requested],
        "schema.approved": [instrumentation.on_approved],
        "schema.rejected": [instrumentation.on_rejected],
        "schema.created": [context.on_schema_created],
        "context.updated": [analytics.on_context_updated],
    })

    app_state = AppState(settings, store, tracer, bus, instrumentation, context, analytics)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _bootstrap(settings, store, context)
        # Provision the Atlys PM agent in LibreChat in the background.
        # This is non-blocking: the FastAPI service starts immediately and the
        # provision script retries until LibreChat is ready (up to 2 minutes).
        asyncio.create_task(_provision_agent_async(settings))
        yield
        try:
            tracer.flush()
        except Exception:  # noqa: BLE001
            pass

    app = FastAPI(title="Atlys Copilot Orchestration Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Conversation-Id"],
    )

    # convenience access for tests/clients (app.state.* mirrors the module global)
    app.state.app_state = app_state
    app.state.store = store
    app.state.bus = bus
    app.state.tracer = tracer
    app.state.instrumentation = instrumentation
    app.state.context = context
    app.state.analytics = analytics
    app.state.settings = settings

    # REST (dashboard read path)
    app.include_router(api.router)

    # MCP over SSE (mounted at /mcp/sse)
    try:
        from .mcp_server import AtlysMcpServer
        mcp = AtlysMcpServer(bus, instrumentation, context, analytics, store, tracer, settings)
        mcp.register_routes(app)
        log.info("MCP server registered at /mcp/sse and /mcp/messages/")
    except Exception as e:  # noqa: BLE001
        log.warning("MCP server not mounted: %s", e)

    @app.get("/healthz")
    def healthz():
        return {
            "status": "ok",
            "mode": "dry-run" if isinstance(store, DryRunStore) else "clickhouse",
            "clickhouse_version": getattr(store, "server_version", None),
            "settings": settings.summary(),
        }

    # Serve the React+Vite UI (built to service/static/ by `npm run build`).
    # In dev mode the Vite dev server runs separately (:5173) and proxies /api/* to :8000.
    # In production / Docker the build output is served from here.
    # NOTE: /healthz must stay registered BEFORE this catch-all mount — a
    # StaticFiles mount at "/" would otherwise shadow it (returns 404).
    _static_dir = Path(__file__).parent / "static"
    if _static_dir.exists():
        # SPA catch-all: serve index.html for any non-API path.
        # Mount must come AFTER /api and /mcp so those take priority.
        from fastapi.responses import FileResponse

        @app.get("/")
        def spa_root():
            return FileResponse(_static_dir / "index.html")

        app.mount("/", StaticFiles(directory=_static_dir, html=True), name="ui")
        log.info("React UI served from %s", _static_dir)
    else:
        log.info(
            "No static/ directory found — UI not served from FastAPI. "
            "Run `cd Atlys/ui && npm run build` to build the React app, "
            "or start the Vite dev server with `npm run dev`."
        )

    return app


def _bootstrap(settings: Settings, store, context: ContextAgent) -> None:
    """Ensure operational tables exist, seed context v0, create flagship MV."""
    ver = getattr(store, "server_version", None)
    if not ver and hasattr(store, "detect_version"):
        try:
            ver = store.detect_version()
        except Exception as e:  # noqa: BLE001
            log.warning("ClickHouse version detection failed: %s", e)
            ver = "unknown"
    log.info("bootstrap starting (ClickHouse version=%s)", ver or "unknown")
    for ddl in DDL_STATEMENTS:
        try:
            store.command(ddl)
        except Exception as e:  # noqa: BLE001
            log.warning("bootstrap DDL failed: %s — %s", ddl.splitlines()[0][:60], e)
    try:
        context.seed_if_empty()
    except Exception as e:  # noqa: BLE001
        log.warning("context seed failed: %s", e)
    try:
        create_mv_funnel_daily(store)
    except Exception as e:  # noqa: BLE001
        log.warning("mv_funnel_daily skipped: %s", e)


async def _provision_agent_async(settings: Settings) -> None:
    """Background task: provision the Atlys PM agent in LibreChat.

    Runs in the asyncio event loop via create_task so it doesn't block startup.
    Uses run_in_executor to avoid blocking the loop during the HTTP wait.
    """
    if not settings.librechat_admin_email or not settings.librechat_admin_password:
        log.warning(
            "LIBRECHAT_ADMIN_EMAIL / LIBRECHAT_ADMIN_PASSWORD not set — "
            "skipping auto-provisioning. Set them in .env and restart to auto-create "
            "the Atlys PM agent, or run `python scripts/provision_agent.py` manually."
        )
        return

    loop = asyncio.get_event_loop()
    try:
        import sys
        sys.path.insert(0, str(settings.atlys_root))
        from scripts.provision_agent import provision  # type: ignore[import]

        agent_id = await loop.run_in_executor(None, provision, settings)
        log.info("Atlys PM agent provisioned: %s", agent_id)
    except Exception as e:  # noqa: BLE001
        log.warning("Agent provisioning failed (non-fatal): %s", e)


app = create_app()

