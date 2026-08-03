from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import ask as ask_module
from . import config, coverage as coverage_module, db, detect, hourly_drilldown, ingest
from . import investigate as investigate_module
from . import metrics, revenue_signals, schemas, thresholds as thresholds_module, timeline as timeline_module, timing

app = FastAPI(title="Why Did It Move - InMobi root-cause backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan", response_model=schemas.ScanResponse)
def scan(req: schemas.ScanRequest):
    return detect.scan(since_day=req.since_day)


@app.get("/api/anomalies")
def list_anomalies(day: Optional[date] = None, status: str = "open"):
    client = db.get_ro_client()
    conditions = []
    params = {}
    # status="all" is a sentinel meaning no filter - used by the anomaly
    # count chart to count every candidate ever detected, not just open ones.
    if status and status != "all":
        conditions.append("status = {status:String}")
        params["status"] = status
    if day:
        conditions.append("day = {day:Date}")
        params["day"] = day
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = client.query(
        f"""
        SELECT id, day, metric, segment_dims, baseline_value, actual_value,
               pct_deviation, z_score, status
        FROM inmobi_rca.anomaly_candidates
        {where_clause}
        ORDER BY day DESC, abs(pct_deviation) DESC
        """,
        parameters=params,
    )
    cols = ["id", "day", "metric", "segment_dims", "baseline_value", "actual_value", "pct_deviation", "z_score", "status"]
    return [dict(zip(cols, r)) for r in result.result_rows]


@app.post("/api/investigate")
def investigate_endpoint(req: schemas.InvestigateRequest):
    if req.metric not in metrics.METRIC_EXPRESSIONS:
        raise HTTPException(status_code=400, detail=f"unknown metric {req.metric!r}")
    try:
        return investigate_module.investigate(req.metric, req.day, req.anomaly_candidate_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    client = db.get_ro_client()
    result = client.query(
        """
        SELECT id, created_at, metric, day, diagnosis_text, responsible_segment,
               checked_and_ruled_out, cited_numbers, confidence, langfuse_trace_id
        FROM inmobi_rca.investigations
        WHERE id = {id:String}
        """,
        parameters={"id": investigation_id},
    )
    if not result.result_rows:
        raise HTTPException(status_code=404, detail="investigation not found")
    cols = [
        "id", "created_at", "metric", "day", "diagnosis_text", "responsible_segment",
        "checked_and_ruled_out", "cited_numbers", "confidence", "langfuse_trace_id",
    ]
    row = dict(zip(cols, result.result_rows[0]))
    row["langfuse_trace_url"] = (
        f"{config.LANGFUSE_WEB_PUBLIC_URL}/trace/{row['langfuse_trace_id']}"
        if row.get("langfuse_trace_id")
        else None
    )
    return row


@app.get("/api/metric-tree")
def metric_tree(day: date):
    client = db.get_ro_client()
    computed_thresholds = thresholds_module.compute_metric_thresholds(client, metrics.HEADLINE_METRICS)
    tree = []
    for metric_name in metrics.HEADLINE_METRICS:
        dev = investigate_module.compute_daily_deviation(client, day, metric_name)
        pct = dev.get("pct_deviation") if dev else None
        pct_threshold = computed_thresholds[metric_name]["pct_threshold"]
        # gray = could not evaluate (no/insufficient baseline history) -
        # distinct from green (evaluated and fine).
        if pct is None:
            status = "gray"
        elif abs(pct) >= pct_threshold * 2:
            status = "red"
        elif abs(pct) >= pct_threshold:
            status = "amber"
        else:
            status = "green"
        tree.append({"metric": metric_name, "status": status, "pct_threshold": pct_threshold, **(dev or {})})
    return tree


@app.post("/api/ask")
def ask_endpoint(req: schemas.AskRequest):
    try:
        context = req.context.model_dump() if req.context else None
        return ask_module.ask(req.question, context=context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metric-history")
def metric_history(metric: str):
    if metric not in metrics.METRIC_EXPRESSIONS:
        raise HTTPException(status_code=400, detail=f"unknown metric {metric!r}")
    client = db.get_ro_client()
    computed_thresholds = thresholds_module.compute_metric_thresholds(client, [metric])
    days = investigate_module.daily_deviation_series(client, metric)
    return {"metric": metric, "pct_threshold": computed_thresholds[metric]["pct_threshold"], "days": days}


@app.get("/api/timeline")
def timeline_endpoint(
    metric: str,
    day: date,
    dimension: Optional[str] = None,
    value: Optional[str] = None,
    dimension2: Optional[str] = None,
    value2: Optional[str] = None,
):
    if metric not in metrics.METRIC_EXPRESSIONS:
        raise HTTPException(status_code=400, detail=f"unknown metric {metric!r}")
    if dimension and dimension not in metrics.DIMENSIONS:
        raise HTTPException(status_code=400, detail=f"unknown dimension {dimension!r}")
    if dimension2 and dimension2 not in metrics.DIMENSIONS:
        raise HTTPException(status_code=400, detail=f"unknown dimension {dimension2!r}")
    client = db.get_ro_client()
    try:
        return timeline_module.get_timeline(client, metric, day, dimension, value, dimension2, value2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/latency-stats")
def latency_stats_endpoint(endpoint: str = "investigate"):
    client = db.get_ro_client()
    return timing.stats(client, endpoint)


@app.get("/api/hour-drilldown")
def hour_drilldown_endpoint(metric: str, hour: datetime):
    if metric not in metrics.METRIC_EXPRESSIONS:
        raise HTTPException(status_code=400, detail=f"unknown metric {metric!r}")
    client = db.get_ro_client()
    try:
        computed_thresholds = thresholds_module.compute_metric_thresholds(client, [metric])
        return hourly_drilldown.investigate_hour(client, hour, metric, computed_thresholds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/day-hour-scan")
def day_hour_scan_endpoint(metric: str, day: date):
    if metric not in metrics.METRIC_EXPRESSIONS:
        raise HTTPException(status_code=400, detail=f"unknown metric {metric!r}")
    client = db.get_ro_client()
    try:
        computed_thresholds = thresholds_module.compute_metric_thresholds(client, [metric])
        hours = hourly_drilldown.day_hour_scan(client, day, metric, computed_thresholds)
        return {"day": day.isoformat(), "metric": metric, "hours": hours}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/revenue-signals")
def revenue_signals_endpoint(day: Optional[date] = None):
    client = db.get_ro_client()
    try:
        cov = coverage_module.day_coverage(client)
        hour_cutoff = coverage_module.hour_cutoff_for(cov, day) if day else None
        computed = thresholds_module.compute_metric_thresholds(client, ["revenue"])
        result = revenue_signals.all_signals(
            client, hour_cutoff=hour_cutoff, volume_floor=computed["revenue"]["volume_floor"]
        )
        if day:
            day_str = str(day)
            for key in ("sustained_drift", "collapsed_segment", "share_shift"):
                result[key] = [s for s in result[key] if str(s["day"]) == day_str]
            result["total"] = sum(len(result[k]) for k in ("sustained_drift", "collapsed_segment", "share_shift"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/events", response_model=schemas.IngestEventsResponse)
def ingest_events_endpoint(req: schemas.IngestEventsRequest):
    try:
        return ingest.insert_events(req.events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
