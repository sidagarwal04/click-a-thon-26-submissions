"""FastAPI app: operational incident console for gold.metric_anomalies."""

from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from inmobi_ops_ui.clickhouse_client import (
    ClickHouseError,
    fetch_incident,
    fetch_incidents,
    fetch_stats,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

app = FastAPI(title="Anomaly Radar", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
def stats() -> dict:
    try:
        return fetch_stats()
    except ClickHouseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/incidents")
def incidents(limit: int = 200) -> list[dict]:
    limit = max(1, min(limit, 500))
    try:
        return fetch_incidents(limit=limit)
    except ClickHouseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/incidents/{anomaly_id}")
def incident_detail(anomaly_id: str) -> dict:
    try:
        row = fetch_incident(anomaly_id)
    except ClickHouseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    evidence = row.get("evidence_json") or ""
    if evidence:
        try:
            row["evidence_parsed"] = json.loads(evidence)
        except json.JSONDecodeError:
            row["evidence_parsed"] = None
    return row


def main() -> None:
    uvicorn.run(
        "inmobi_ops_ui.app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
    )


if __name__ == "__main__":
    main()
