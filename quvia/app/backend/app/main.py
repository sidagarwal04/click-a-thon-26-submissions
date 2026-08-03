from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from langfuse import observe
from pydantic import BaseModel

from . import db, librechat_auth, llm, narrate

app = FastAPI(title="AeroOps/AdOps RCA Dashboard")


@app.middleware("http")
async def redirect_0000_to_localhost(request: Request, call_next):
    # "0.0.0.0:8000" is what `docker ps` prints for this port mapping, so
    # it's an easy accidental copy-paste — but it's a bind address, not a
    # real hostname, and cookies are matched by exact hostname string. The
    # embedded LibreChat auto-login relies on this app and LibreChat sharing
    # the literal "localhost" host, so 0.0.0.0 silently breaks it. Nobody
    # legitimately needs to browse to 0.0.0.0 itself, so this redirect is safe.
    host = request.headers.get("host", "")
    if host.startswith("0.0.0.0"):
        new_host = host.replace("0.0.0.0", "localhost", 1)
        url = request.url.replace(netloc=new_host)
        return RedirectResponse(url=str(url))
    return await call_next(request)


class DrilldownSummaryRequest(BaseModel):
    dimension_name: str
    rows: List[Dict[str, Any]]


class IncidentSummaryRequest(BaseModel):
    detection: Dict[str, Any]
    factors: Dict[str, Any]
    contribution: List[Dict[str, Any]]


@app.middleware("http")
async def no_cache_static(request, call_next):
    # This app is under active development during the hackathon — never let
    # browsers serve a stale frontend from cache without revalidating.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/anomalies")
@observe()
def anomalies():
    return db.list_anomalies()


@app.get("/api/incident/{bucket}")
@observe()
def incident(bucket: str, top_n: int = 5, freq: str = "1h"):
    if freq not in db.FREQUENCIES:
        raise HTTPException(400, f"Unknown freq {freq!r}. Must be one of {db.FREQUENCIES}")
    try:
        parsed = db.parse_bucket(bucket)
    except ValueError:
        raise HTTPException(400, f"Invalid bucket datetime: {bucket!r}")

    detection = db.get_detection(parsed)
    if detection is None:
        raise HTTPException(404, f"No agg_overall_1h data (or insufficient history) for bucket {bucket}")

    trend = db.get_day_trend(parsed.date())
    # Contribution ranking respects the selected agg level (1h/6h) — snapped
    # to that granularity's bucket boundary (e.g. 23:00 -> 18:00 for 6h) —
    # but always for THIS incident's specific time, not a calendar range.
    contribution = db.get_contribution(parsed, dimension_names=None, top_n=top_n, freq_key=freq)
    # py's anomaly_overall_1h already carries requests/fill_rate/ecpm z-scores
    # and pct-changes alongside revenue — no separate factor query needed.
    factors = {
        "requests_pct_change": detection["requests_pct_change"],
        "fill_rate_pct_change": detection["fill_rate_pct_change"],
        "ecpm_pct_change": detection["ecpm_pct_change"],
    }
    narration = narrate.build_diagnosis(detection, factors, contribution)

    return JSONResponse(content=_jsonable({
        "detection": detection,
        "trend": trend,
        "contribution": contribution,
        "factors": factors,
        **narration,
    }))


@app.get("/api/dimension/{bucket}/{dimension_name}")
@observe()
def dimension_drilldown(bucket: str, dimension_name: str, top_n: int = 10, freq: str = "1h"):
    if dimension_name not in db.DIMENSIONS:
        raise HTTPException(400, f"Unknown dimension {dimension_name!r}. Must be one of {db.DIMENSIONS}")
    if freq not in db.FREQUENCIES:
        raise HTTPException(400, f"Unknown freq {freq!r}. Must be one of {db.FREQUENCIES}")
    try:
        parsed = db.parse_bucket(bucket)
    except ValueError:
        raise HTTPException(400, f"Invalid bucket datetime: {bucket!r}")

    rows = db.get_contribution(parsed, dimension_names=[dimension_name], top_n=top_n, freq_key=freq)
    return _jsonable(rows)


@app.post("/api/summarize-dimension")
@observe()
def summarize_dimension(payload: DrilldownSummaryRequest):
    # Takes the exact rows the frontend already rendered in the Drill-down
    # table (not a fresh ClickHouse query) so the summary can never drift
    # from what the user is looking at — Claude only phrases these numbers,
    # never sources its own.
    summary = llm.summarize_drilldown(payload.dimension_name, payload.rows)
    if summary is None:
        return {"summary": None, "available": False}
    return {"summary": summary, "available": True}


@app.post("/api/librechat-auto-login")
def librechat_auto_login(response: Response):
    # Logs into the shared LibreChat demo account server-to-server and
    # forwards the Set-Cookie headers it issued onto OUR response — the
    # browser then holds those cookies for hostname "localhost" and sends
    # them to LibreChat's own origin (different port, same host) too, so its
    # iframe boots straight into a session instead of showing its login form.
    cookies = librechat_auth.login_and_get_cookies()
    if not cookies:
        return {"ok": False}
    for cookie_header in cookies:
        response.headers.append("set-cookie", cookie_header)
    return {"ok": True}


@app.post("/api/summarize-incident")
@observe()
def summarize_incident(payload: IncidentSummaryRequest):
    # Same traceability rule as /api/summarize-dimension: takes the exact
    # detection/factors/contribution the frontend already fetched and
    # rendered (KPIs, factor tiles, radar) — Claude only phrases these
    # numbers, it never queries ClickHouse or sees anything not shown on
    # screen.
    summary = llm.summarize_incident(payload.detection, payload.factors, payload.contribution)
    if summary is None:
        return {"summary": None, "available": False}
    return {"summary": summary, "available": True}


@app.get("/api/dimension-trend/{dimension_name}")
@observe()
def dimension_trend(dimension_name: str, start: str, end: str, freq: str = "1h", metric: str = "revenue"):
    if dimension_name not in db.TREND_DIMENSIONS:
        raise HTTPException(400, f"Unknown dimension {dimension_name!r}. Must be one of {db.TREND_DIMENSIONS}")
    if freq not in db.FREQUENCIES:
        raise HTTPException(400, f"Unknown freq {freq!r}. Must be one of {db.FREQUENCIES}")
    if metric not in db.METRICS:
        raise HTTPException(400, f"Unknown metric {metric!r}. Must be one of {list(db.METRICS)}")
    try:
        start_parsed = db.parse_bucket(start)
        end_parsed = db.parse_bucket(end)
    except ValueError:
        raise HTTPException(400, f"Invalid start/end datetime: {start!r} / {end!r}")
    if start_parsed > end_parsed:
        raise HTTPException(400, "start must not be after end")

    return _jsonable(db.get_dimension_series(dimension_name, start_parsed, end_parsed, freq, metric))


@app.get("/api/data-range")
def data_range():
    return {"min": db.DATA_MIN_DATE.isoformat(), "max": db.DATA_MAX_DATE.isoformat()}


def _jsonable(obj):
    """clickhouse-connect returns datetime/date objects; make them JSON-safe."""
    import datetime as dt

    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    return obj


# Static frontend last, so /api/* routes above take precedence.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
