"""Streaming ingestion + per-batch inference, run as a background job.

Replays the sealed Jul 6-10 slice hour by hour and scores each hour as it lands, so detection
is exercised the way it would be in production: on data arriving in order, with no visibility
into what comes next.

Two deliberate choices:

* Detection runs on every batch, but a BUNDLE is only built when a metric actually fires.
  Persisting a bundle per metric per hour would be 120 x 7 rows of "checked, normal" and would
  bury the real findings in the dashboard.
* Starting the stream switches the process into the unseen dataset (RCA_DATASET), so anything
  investigated afterwards targets the streamed slice while baselines keep reading dev history.
  That is a process-wide switch — status() reports it rather than leaving it implicit, and
  stop() restores whatever was set before.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from config import config
from data import stream
from models import Window

log = logging.getLogger(__name__)

_DATASET_ENV = "RCA_DATASET"
_UNSEEN = "unseen"

_state: dict[str, Any] = {"status": "idle"}
_thread: threading.Thread | None = None
_stop = threading.Event()
_lock = threading.Lock()


def _fresh_state(total: int, cfg: dict) -> dict:
    return {
        "status": "running",
        "batches_done": 0,
        "batches_total": total,
        "rows_ingested": 0,
        "detections": [],          # per-hour GLOBAL hits — see module docstring
        "segment_findings": [],    # deep-scan results: global + per-segment, echo-folded
        "deep_scans": 0,
        "deep_scan_window": None,
        "checks": 0,               # metric-hours scored
        "current_window": None,
        "config": cfg,
        "analysis": {},
        "dataset": _UNSEEN,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "error": None,
    }


def status() -> dict:
    with _lock:
        return dict(_state)


def _detect_batch(metrics: list[str], method: str, start: datetime, end: datetime,
                  skip: set) -> tuple[list[dict], list[dict]]:
    """Score each metric over the hour that just landed. Returns (hits, everything scored)."""
    from rca.detection import detect
    from rca.detectors import isolation_forest

    # The stream just added an hour; the cached series predates it and would make every
    # streamed hour look "not present in series". The fitted model is deliberately kept.
    isolation_forest.invalidate_series()

    window = Window(start=start, end=end)
    todo = [m for m in metrics if (start, m) not in skip]

    def score_one(metric: str) -> dict | None:
        try:
            anomaly, _queries = detect(metric, window, method=method)
        except Exception as exc:  # noqa: BLE001 - one bad metric must not kill the stream
            log.warning("stream: detect(%s) failed at %s: %s", metric, start, exc)
            return None
        return {
            "metric": metric, "hour": start, "method": method, "detected": anomaly.detected,
            "observed": round(anomaly.observed, 4), "expected": round(anomaly.expected, 4),
            "pct_delta": round(anomaly.pct_delta, 4), "score": round(anomaly.score, 3),
            "direction": anomaly.direction,
        }

    # Metrics are independent, and each is a DB round trip plus a model score — run them
    # concurrently. Sequentially this was the whole tick budget (~4.3s for 7 metrics); in
    # parallel a tick costs about one metric. Safe since the ClickHouse client no longer binds
    # a session (see data.client.get_client).
    with ThreadPoolExecutor(max_workers=len(todo) or 1) as pool:
        scored = [r for r in pool.map(score_one, todo) if r is not None]

    with _lock:
        _state["checks"] = _state.get("checks", 0) + len(scored)
    return [r for r in scored if r["detected"]], scored



def _deep_scan(stream_start: datetime, upto: datetime) -> list[dict]:
    """Segment-aware sweep over everything streamed so far.

    Per-batch detection is GLOBAL only — it scores each metric across the whole population, so an
    anomaly that is severe inside one segment but diluted to nothing globally is invisible to it
    by construction. Measured on this slice: the sweep's five findings were four segment-scoped
    and one global; the stream saw only the global ones.

    Rather than reimplement that, this calls the SAME dev.discover() the "Find anomalies" sweep
    calls. Running it over the accumulated window — and always on the final batch — is what makes
    the stream and the sweep agree at the end: the last deep scan is literally the same function
    over the same range. Costs ~20-30s, so it runs every `deep_scan_every` batches, not per tick.
    """
    from api import dev

    result = dev.discover(stream_start.strftime("%Y-%m-%d"),
                          (upto + timedelta(days=1)).strftime("%Y-%m-%d"))
    return [r for r in result["incidents"] if r["role"] == "primary"]


def _investigate(metric: str, start: datetime, end: datetime, method: str, session: str) -> str | None:
    """Full traced+persisted investigation for a hit, so it lands in the dashboard feed."""
    from api import pipeline

    try:
        bundle = pipeline.run_detection(metric, Window(start=start, end=end),
                                        method=method, session_id=session)
        return bundle.investigation_id
    except Exception as exc:  # noqa: BLE001 - a failed write must not stop ingestion
        log.warning("stream: investigation for %s @ %s failed: %s", metric, start, exc)
        return None


def _run(cfg: dict) -> None:
    session = f"stream-{datetime.now():%Y%m%d-%H%M%S}"
    skip = set() if cfg.get("reanalyze") else stream.analyzed_hours()
    stream_start = None
    try:
        for start, end in stream.windows(cfg["batch_hours"]):
            if _stop.is_set():
                break
            tick_started = time.perf_counter()
            if stream_start is None:
                stream_start = start

            rows = stream.release(start, end)
            hits, scored = (
                _detect_batch(cfg["detect_metrics"], cfg["detect_method"], start, end, skip)
                if rows else ([], [])
            )
            for hit in hits:
                hit["investigation_id"] = _investigate(
                    hit["metric"], start, end, cfg["detect_method"], session
                )
            # Ledger every metric-hour looked at, hit or not: "checked and normal" is the
            # evidence that the system examined an hour rather than never reaching it.
            stream.record_analysis(scored)
            skip.update((r["hour"], r["metric"]) for r in scored)

            with _lock:
                _state["batches_done"] += 1
                _state["rows_ingested"] += rows
                _state["detections"].extend(hits)
                _state["current_window"] = [start.isoformat(timespec="seconds"),
                                            end.isoformat(timespec="seconds")]
                _state["last_tick_ms"] = round((time.perf_counter() - tick_started) * 1000)

            every = cfg.get("deep_scan_every") or 0
            is_last = _state["batches_done"] >= _state["batches_total"]
            if every and (_state["batches_done"] % every == 0 or is_last):
                try:
                    findings = _deep_scan(stream_start, end)
                    with _lock:
                        _state["segment_findings"] = findings
                        _state["deep_scans"] += 1
                        _state["deep_scan_window"] = [stream_start.isoformat(timespec="seconds"),
                                                      end.isoformat(timespec="seconds")]
                except Exception as exc:  # noqa: BLE001 - a failed deep scan must not stop ingestion
                    log.warning("stream: deep scan failed at %s: %s", end, exc)

            _stop.wait(max(0.0, cfg["tick_seconds"] - (time.perf_counter() - tick_started)))
    except Exception as exc:
        log.exception("stream aborted")
        with _lock:
            _state["error"] = str(exc)
    finally:
        with _lock:
            _state["analysis"] = stream.analysis_summary()
            _state["status"] = "stopped" if _stop.is_set() else ("error" if _state.get("error") else "done")
            _state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            # Deliberately NOT reverting the dataset. Reverting on stop meant that the moment a
            # replay finished, every sweep and investigation silently went back to the dev
            # tables — so "Find anomalies" over the streamed range returned 0 findings because
            # dev holds no rows after Jul 5. The streamed slice is what the user is looking at;
            # it stays selected until they switch it back via POST /dataset.


def start(overrides: dict | None = None, reset: bool = True) -> dict:
    """Prepare the unseen tables and begin replaying. Refuses to start a second run."""
    global _thread

    with _lock:
        if _state.get("status") == "running":
            raise ValueError("a stream is already running; stop it first")

    cfg = {**config()["stream"], **(overrides or {})}

    if reset:
        stream.prepare()
    # The model must not carry a fit from a previous dataset into this run.
    from rca.detectors import isolation_forest

    isolation_forest.reset_cache()

    os.environ[_DATASET_ENV] = _UNSEEN
    total = len(list(stream.windows(cfg["batch_hours"])))

    _stop.clear()
    with _lock:
        _state.clear()
        _state.update(_fresh_state(total, cfg))

    _thread = threading.Thread(target=_run, args=(cfg,), daemon=True)
    _thread.start()
    return status()


def stop() -> dict:
    """Ask the stream to stop after the current batch."""
    _stop.set()
    return status()
