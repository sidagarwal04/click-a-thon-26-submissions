"""FastAPI layer over the investigation engine.

Two kinds of endpoint, and the split matters:

  * The investigation itself is *precomputed*. A full run takes ~4s of query
    time plus ~25s of narration, which is fine for a harness and far too slow
    for a page load. `GET /api/v1/investigation` serves the last completed run;
    `POST /api/v1/investigate` recomputes on demand.

  * The chart data is *live*. `GET /api/v1/timeseries` and `/segments` query
    ClickHouse per request and carry the full latency envelope, because the
    point of showing them is that ClickHouse answers in milliseconds over
    millions of rows. A cached number proves nothing.

Every live endpoint returns query_ms, wall_ms, rows_scanned and the SQL it ran.
Publishing only server time overstates how fast the UI feels; publishing only
wall time understates ClickHouse. Both, labelled, so "is that really end to
end?" has a straight answer.
"""
import asyncio
import inspect
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import clickhouse_connect
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.db import _load_env  # noqa: E402

OUT_FILE = REPO / "out" / "diagnosis.json"


class Envelope(BaseModel):
    """Every live endpoint returns this. The latency badge reads it."""
    data: list[dict[str, Any]]
    query_ms: float      # ClickHouse server time
    wall_ms: float       # server time + network round trip — what the user waits
    rows_scanned: int
    sql: str             # the exact query, so a panel can explain itself


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_env()
    app.state.ch = await clickhouse_connect.get_async_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
        username=os.getenv("CLICKHOUSE_USER", "dashboard_ro"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "inmobi"),
        secure=os.getenv("CLICKHOUSE_SECURE", "true").lower() == "true",
    )
    app.state.investigation = _load_from_disk()
    app.state.investigation_mtime = OUT_FILE.stat().st_mtime if OUT_FILE.exists() else None
    app.state.running = False
    yield
    # close() is a coroutine in clickhouse-connect 1.6 and sync in some other
    # versions. Awaiting unconditionally raises; never awaiting leaks.
    closer = app.state.ch.close()
    if inspect.isawaitable(closer):
        await closer


_load_env()  # OTel config is read at import time, before lifespan runs
app = FastAPI(title="InMobi RCA", lifespan=lifespan)


def _instrument_otel(application: FastAPI) -> bool:
    """Export API traces to ClickStack/HyperDX.

    Langfuse traces the *investigation's reasoning*; this traces the *service*
    — request latency, which endpoint, where the time went. Two different
    questions, which is why both exist rather than one being redundant.

    Best-effort, like the Langfuse tracer: an observability backend being
    unreachable must never take out the thing it observes.
    """
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", "inmobi-rca-api"),
        }))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(application)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  [otel] disabled: {exc}")
        return False


OTEL_ENABLED = _instrument_otel(app)

app.add_middleware(
    CORSMiddleware,
    # Must list the exact scheme+host+port the browser used. A LAN or tailnet
    # origin is a different origin from localhost, and that mismatch is the
    # classic afternoon time sink.
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3100,http://127.0.0.1:3100",
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_from_disk() -> dict[str, Any] | None:
    if OUT_FILE.exists():
        try:
            return json.loads(OUT_FILE.read_text())
        except json.JSONDecodeError:
            # A run mid-write leaves truncated JSON. Returning None here would
            # blank the UI; callers keep the previous copy instead.
            return None
    return None


def _current_investigation() -> dict[str, Any] | None:
    """The last completed run, re-read whenever the file on disk has changed.

    Loading once at startup meant every fresh ./investigate.sh silently served
    stale results until someone remembered to restart the API — which reliably
    nobody does, and which looks like the engine failing rather than the server
    caching. An mtime check costs one stat() per request and removes the whole
    failure mode.
    """
    if not OUT_FILE.exists():
        return app.state.investigation
    mtime = OUT_FILE.stat().st_mtime
    if mtime != getattr(app.state, "investigation_mtime", None):
        fresh = _load_from_disk()
        if fresh is not None:            # keep the last good copy on a partial write
            app.state.investigation = fresh
            app.state.investigation_mtime = mtime
    return app.state.investigation


async def run(sql: str, params: dict) -> Envelope:
    t0 = time.perf_counter()
    try:
        result = await app.state.ch.query(sql, parameters=params)
    except Exception as exc:  # noqa: BLE001
        # Never swallow into an empty list. A silent empty chart at 3am costs
        # an hour of debugging the wrong layer.
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc
    wall_ms = (time.perf_counter() - t0) * 1000
    summary = result.summary or {}   # summary can be absent; .get on None throws
    return Envelope(
        data=[dict(zip(result.column_names, row)) for row in result.result_rows],
        query_ms=round(float(summary.get("elapsed_ns", 0)) / 1e6, 2),
        wall_ms=round(wall_ms, 2),
        rows_scanned=int(summary.get("read_rows", 0) or 0),
        sql=" ".join(sql.split()),
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
async def health():
    """Two seconds to tell whether it's the API or the database."""
    try:
        await app.state.ch.query("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"clickhouse unreachable: {exc}") from exc
    return {
        "status": "ok",
        "clickhouse": "reachable",
        "investigation_loaded": app.state.investigation is not None,
        "investigation_running": app.state.running,
        # Deliberately probed, not assumed. The first version of this reported
        # otel_exporting: true whenever instrumentation *set up* successfully —
        # while every span was being rejected 401 by the collector. A health
        # check that reports configuration rather than function is the same
        # failure as a green handshake on a credential that never authenticated.
        "otel": await _otel_status(),
    }


async def _otel_status() -> dict[str, Any]:
    """Actually ask the collector whether it would accept our spans."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or not OTEL_ENABLED:
        return {"configured": False, "exporting": False,
                "detail": "OTEL_EXPORTER_OTLP_ENDPOINT not set"}

    headers = {}
    for pair in os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "").split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            headers[k.strip()] = v.strip()

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{endpoint.rstrip('/')}/v1/traces",
                json={"resourceSpans": []},
                headers={"content-type": "application/json", **headers},
                timeout=aiohttp.ClientTimeout(total=4),
            ) as resp:
                if resp.status == 401:
                    return {"configured": True, "exporting": False,
                            "detail": "collector rejects the ingestion key (401) — "
                                      "get the real one from HyperDX → Team Settings"}
                if resp.status >= 400:
                    return {"configured": True, "exporting": False,
                            "detail": f"collector returned {resp.status}"}
                return {"configured": True, "exporting": True, "endpoint": endpoint}
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "exporting": False, "detail": f"unreachable: {exc}"}


# ---------------------------------------------------------------------------
# The investigation — precomputed
# ---------------------------------------------------------------------------

@app.get("/api/v1/investigation")
async def investigation():
    """The last completed investigation, exactly as the harness wrote it.

    This is the same shape as out/diagnosis.json, deliberately: the file is the
    contract the UI was built against, so there is nothing to reshape here.
    """
    inv = _current_investigation()
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail="no investigation available — run ./investigate.sh first",
        )
    return inv


@app.get("/api/v1/events/{index}")
async def event_detail(index: int):
    """One event by 1-based index, with its narration attached."""
    inv = _current_investigation()
    if inv is None:
        raise HTTPException(status_code=404, detail="no investigation available")
    events = inv.get("events", [])
    if not 1 <= index <= len(events):
        raise HTTPException(
            status_code=404,
            detail=f"event {index} not found ({len(events)} available)",
        )
    return {
        "event": events[index - 1],
        "narration": inv.get("narrations", {}).get(str(index)),
        "trace_url": inv.get("trace_url"),
    }


class InvestigateRequest(BaseModel):
    start: str | None = None
    end: str | None = None
    weeks: int = 4
    narrate: bool = True
    max_narrate: int = 3


@app.post("/api/v1/investigate")
async def investigate_now(req: InvestigateRequest):
    """Recompute. Blocking and slow by design — a manual trigger, not a poll.

    The engine is synchronous, so it runs in a worker thread rather than
    stalling the event loop and freezing every other request for 30 seconds.
    """
    if app.state.running:
        raise HTTPException(status_code=409, detail="an investigation is already running")

    app.state.running = True
    try:
        result = await asyncio.to_thread(_run_investigation_sync, req)
    finally:
        app.state.running = False

    app.state.investigation = result
    return result


def _run_investigation_sync(req: InvestigateRequest) -> dict[str, Any]:
    from engine.db import DB
    from engine.investigate import investigate as run_investigation
    from engine.narrate import narrate
    from engine.trace import make_tracer

    db = DB()
    start, end = req.start, req.end
    if not (start and end):
        row = db.query(
            "SELECT min(hour) AS lo, max(hour) AS hi FROM inmobi.events_hourly",
            label="api:window",
        ).first()
        start, end = start or str(row["lo"]), end or str(row["hi"])

    tracer = make_tracer(name="rca-investigation-api",
                         metadata={"window": [start, end], "source": "api"})
    inv = run_investigation(db, start, end, weeks=req.weeks, tracer=tracer)

    narrations: dict[str, Any] = {}
    if req.narrate:
        for n, event in enumerate(inv.events[: req.max_narrate], 1):
            try:
                result = narrate(event.to_dict())
            except Exception:  # noqa: BLE001 — narration must not sink the run
                continue
            narrations[str(n)] = {
                "text": result.text,
                "model": result.model,
                "all_numbers_verified": result.all_numbers_verified,
                "unverified_numbers": result.unverified_numbers,
            }

    if hasattr(tracer, "close"):
        tracer.close(output={"events": len(inv.events)})

    payload = json.loads(json.dumps(inv.to_dict(), default=str))
    payload["narrations"] = narrations
    return payload


# ---------------------------------------------------------------------------
# Live chart data — full envelope, queried per request
# ---------------------------------------------------------------------------

METRIC_SQL = {
    "revenue": "revenue",
    "requests": "requests",
    "fill_rate": "if(requests > 0, fills / requests, 0)",
    "render_rate": "if(fills > 0, impressions / fills, 0)",
    "ecpm": "if(impressions > 0, revenue / impressions * 1000, 0)",
    "ctr": "if(impressions > 0, clicks / impressions, 0)",
}


@app.get("/api/v1/timeseries", response_model=Envelope)
async def timeseries(
    metric: str = Query("revenue"),
    start: str = Query(...),
    end: str = Query(...),
    weeks: int = Query(4, ge=1, le=8),
    dim_name: str | None = Query(None),
    dim_value: str | None = Query(None),
):
    """Hourly actual against its like-for-like baseline.

    This is the chart that shows the metric dropping — the visual the whole
    demo hangs on. The baseline is the median of the same weekday and hour over
    the trailing weeks, matching the detector exactly, so the line the UI draws
    is the line the engine judged against rather than a second opinion.

    Pass dim_name + dim_value to scope to one segment (reads the unpivoted
    rollup); omit both for the platform total (reads the hourly rollup).
    """
    if metric not in METRIC_SQL:
        raise HTTPException(
            status_code=400,
            detail=f"unknown metric '{metric}'; expected one of {sorted(METRIC_SQL)}",
        )
    expr = METRIC_SQL[metric]

    if dim_name and dim_value:
        source = "inmobi.events_hourly_by_dim"
        scope = "AND dim_name = {dim_name:String} AND dim_value = {dim_value:String}"
    elif dim_name or dim_value:
        raise HTTPException(
            status_code=400, detail="dim_name and dim_value must be given together"
        )
    else:
        source = "inmobi.events_hourly"
        scope = ""

    sql = f"""
    WITH
        target AS (
            SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   {expr} AS metric_value
            FROM {source}
            WHERE hour >= {{start:DateTime}} AND hour <= {{end:DateTime}} {scope}
        ),
        hist AS (
            SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   {expr} AS metric_value
            FROM {source}
            WHERE hour < {{end:DateTime}} {scope}
        )
    SELECT
        t.hour                             AS hour,
        t.metric_value                     AS actual,
        quantileExact(0.5)(h.metric_value) AS baseline,
        count()                            AS baseline_samples
    FROM target AS t
    INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod
    WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({{weeks:UInt8}})
    GROUP BY t.hour, t.metric_value
    ORDER BY t.hour
    """
    params = {"start": start, "end": end, "weeks": weeks}
    if dim_name and dim_value:
        params |= {"dim_name": dim_name, "dim_value": dim_value}
    return await run(sql, params)


@app.get("/api/v1/segments", response_model=Envelope)
async def segments(
    dimension: str = Query(...),
    metric: str = Query("revenue"),
    start: str = Query(...),
    end: str = Query(...),
    weeks: int = Query(4, ge=1, le=8),
):
    """Per-value actual vs baseline for one dimension over the window.

    Backs the evidence table under a responsible or ruled-out dimension. Ratios
    are recomputed sum/sum per value here, never averaged across values.
    """
    if metric not in METRIC_SQL:
        raise HTTPException(
            status_code=400,
            detail=f"unknown metric '{metric}'; expected one of {sorted(METRIC_SQL)}",
        )
    expr = METRIC_SQL[metric]

    sql = f"""
    WITH
        actual AS (
            SELECT dim_value,
                   sum(requests) AS requests, sum(fills) AS fills,
                   sum(impressions) AS impressions, sum(clicks) AS clicks,
                   sum(revenue) AS revenue
            FROM inmobi.events_hourly_by_dim
            WHERE dim_name = {{dimension:String}}
              AND hour >= {{start:DateTime}} AND hour <= {{end:DateTime}}
            GROUP BY dim_value
        ),
        prior AS (
            SELECT dim_value,
                   sum(requests) AS requests, sum(fills) AS fills,
                   sum(impressions) AS impressions, sum(clicks) AS clicks,
                   sum(revenue) AS revenue
            FROM inmobi.events_hourly_by_dim
            WHERE dim_name = {{dimension:String}}
              AND hour >= {{start:DateTime}} - toIntervalWeek({{weeks:UInt8}})
              AND hour <  {{start:DateTime}}
            GROUP BY dim_value
        )
    SELECT
        a.dim_value                                         AS dim_value,
        {expr.replace('requests', 'a.requests').replace('fills', 'a.fills')
             .replace('impressions', 'a.impressions').replace('clicks', 'a.clicks')
             .replace('revenue', 'a.revenue')}              AS actual,
        {expr.replace('requests', 'p.requests').replace('fills', 'p.fills')
             .replace('impressions', 'p.impressions').replace('clicks', 'p.clicks')
             .replace('revenue', 'p.revenue')}              AS baseline_total,
        a.requests                                          AS requests,
        a.revenue                                           AS revenue
    FROM actual AS a
    INNER JOIN prior AS p USING (dim_value)
    ORDER BY a.revenue DESC
    """
    return await run(sql, {"dimension": dimension, "start": start,
                           "end": end, "weeks": weeks})
