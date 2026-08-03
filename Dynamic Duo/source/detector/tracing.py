"""Investigation tracing: the log_step contract between the RCA agent and the platform.

One call records a step in TWO places (each independent, each optional-degradable):
  1. rca.investigation_steps  — always; the queryable trace judges can replay
  2. OTLP/HTTP collector      — when OTEL_EXPORTER_OTLP_ENDPOINT set
                                (ClickStack's collector, http://host:4318)

Zero dependencies: OTLP speaks OTLP/JSON via urllib. A missing endpoint degrades
silently to CH-only (one notice per process), so the agent runs identically with
or without the observability stack attached.

Agent usage (Nitya):
    from detector.tracing import Investigation

    inv = Investigation("inc_20260623T00_fill_rate_global")   # picks up after 'detect'
    inv.step("decompose",
             hypothesis="which lever of the revenue identity moved?",
             sql_text=q1_sql, result=q1_rows, decision="fill_rate moved -3.46pp -> fill drill")
    ...
    inv.generation(model="gpt-5-nano", completion=narrative,
                   usage={"input": 1200, "output": 300})      # the narrator call
    inv.close(status="diagnosed")

The trace id is `<incident_id>-run-<run_id>`: scoped to the RUN, so re-investigating
an incident produces a NEW trace rather than appending spans onto the previous run's
trace (which keeps its original start time and reads as hours-old). Always store
`inv.trace_id` in diagnoses.trace_id — each stored diagnosis then deep-links to exactly
the run that produced it. The incident id stays in the root span's name and on every
span's `rca.incident_id`, so searching by incident still finds every run.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from . import chdb

_WARNED: set[str] = set()


def _warn_once(key: str, msg: str) -> None:
    if key not in _WARNED:
        _WARNED.add(key)
        print(f"[tracing] {msg}")


def _post_json(url: str, payload: dict, headers: dict) -> bool:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError) as e:
        _warn_once(url, f"export to {url} failed ({e}); continuing with ClickHouse-only trace")
        return False


class _Otlp:
    def __init__(self):
        self.endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
        self.enabled = bool(self.endpoint)
        # standard OTEL_EXPORTER_OTLP_HEADERS: "k=v,k2=v2". ClickStack ingestion
        # requires "authorization=<team ingestion API key>" (librechat/wire_traces.sh)
        self.headers = {}
        for pair in os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "").split(","):
            if "=" in pair:
                k, _, v = pair.partition("=")
                self.headers[k.strip()] = v.strip()
        if not self.enabled:
            _warn_once("otlp", "OTEL_EXPORTER_OTLP_ENDPOINT unset — OTLP export off")

    def send_span(self, trace_hex: str, name: str, start_ns: int, end_ns: int,
                  attributes: dict, span_id: str | None = None,
                  parent_span_id: str | None = None) -> None:
        if not self.enabled:
            return
        def val(v):
            if isinstance(v, bool):
                return {"boolValue": v}
            if isinstance(v, int):
                return {"intValue": str(v)}
            if isinstance(v, float):
                return {"doubleValue": v}
            return {"stringValue": str(v)[:4000]}
        attrs = [{"key": k, "value": val(v)} for k, v in attributes.items() if v is not None]
        span = {
            "traceId": trace_hex,
            "spanId": span_id or uuid.uuid4().hex[:16],
            "name": name,
            "kind": 1,
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": attrs,
        }
        if parent_span_id:
            span["parentSpanId"] = parent_span_id
        payload = {"resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "rca-investigator"}}]},
            "scopeSpans": [{"scope": {"name": "rca"}, "spans": [span]}],
        }]}
        _post_json(f"{self.endpoint}/v1/traces", payload, self.headers)


class Investigation:
    """Trace context for one incident. step_no continues after the sweep's detect row."""

    def __init__(self, incident_id: str, metadata: dict | None = None):
        self.incident_id = incident_id                    # ClickHouse key — never scoped
        # Trace identity is scoped to the RUN, not the incident. Keying it on the
        # incident alone made every re-run replay byte-identical trace/span ids,
        # merging new spans onto the previous run's trace — which keeps its original
        # start time, so a clean run's traces silently read hours old and sort to
        # the bottom instead of appearing as new. The incident id stays in the root
        # span name (searchable) and the prefix (readable in a URL).
        self.run_id = uuid.uuid4().hex[:8]
        self.trace_id = f"{incident_id}-run-{self.run_id}"  # stored in diagnoses.trace_id
        self.trace_hex = hashlib.md5(self.trace_id.encode()).hexdigest()  # OTel 128-bit id
        self.root_span = self.trace_hex[:16]              # per-run root span id
        self.t0_ns = int(time.time() * 1e9)               # investigation start (root span)
        self.otlp = _Otlp()
        nxt = chdb.scalar(
            "SELECT coalesce(max(toNullable(step_no)), -1) + 1 FROM rca.investigation_steps "
            "WHERE incident_id = {inc:String}", {"inc": incident_id})
        self.step_no = int(nxt)
        # incident context stamped on every span so HyperDX searches work
        # (metric:fill_rate, scope:global, ...); degrade to empty if row not yet written
        self.ctx: dict = {}
        try:
            rows = chdb.query(
                "SELECT metric, scope, toString(window_start) AS ws, toString(window_end) AS we "
                "FROM rca.incidents FINAL WHERE incident_id = {inc:String}", {"inc": incident_id})
            if rows:
                self.ctx = {"rca.metric": rows[0]["metric"], "rca.scope": rows[0]["scope"],
                            "rca.window_start": rows[0]["ws"], "rca.window_end": rows[0]["we"]}
        except Exception:
            pass

    def step(self, step_type: str, hypothesis: str, sql_text: str,
             result, decision: str, duration_ms: int | None = None) -> int:
        """Record one investigation step everywhere. Returns its step_no."""
        t_end = datetime.now(timezone.utc)
        dur = int(duration_ms or 0)
        result_json = result if isinstance(result, str) else json.dumps(result, default=str)
        n = self.step_no
        chdb.insert_rows("rca.investigation_steps", [{
            "incident_id": self.incident_id, "step_no": n, "step_type": step_type,
            "hypothesis": hypothesis, "sql_text": sql_text,
            "result": result_json, "decision": decision, "duration_ms": dur,
        }])
        end_ns = int(t_end.timestamp() * 1e9)
        self.otlp.send_span(
            self.trace_hex, f"{n:02d} {step_type}",
            end_ns - dur * 1_000_000, end_ns,
            {
                "rca.incident_id": self.incident_id,
                "rca.step_no": n,
                "rca.step_type": step_type,
                "rca.hypothesis": hypothesis,
                "rca.decision": decision,
                "rca.result": result_json[:4000],
                "rca.duration_ms": dur,
                "db.system": "clickhouse",
                "db.statement": sql_text,          # HyperDX renders this as the query
                **self.ctx,
            },
            span_id=f"{self.trace_hex[:12]}{n:04x}",   # deterministic per step
            parent_span_id=self.root_span)
        self.step_no += 1
        return n

    def generation(self, model: str, completion: str,
                   usage: dict | None = None, duration_ms: int | None = None) -> int:
        """Record the narrator LLM call as a 'narrate' step (model + token usage;
        the narrative itself is persisted in diagnoses once the guardrail passes)."""
        return self.step(
            "narrate",
            hypothesis="LLM narrates from the evidence bundle; computes nothing",
            sql_text="-- no SQL: input is the evidence bundle (see result)",
            result={"model": model, "usage": usage or {}},
            decision=f"narrative drafted ({len(completion)} chars), pending guardrail",
            duration_ms=duration_ms)

    def close(self, status: str, headline: str | None = None) -> None:
        """Update the incident's status ('investigating' -> terminal state)."""
        chdb.query_raw(
            "INSERT INTO rca.incidents SELECT incident_id, run_id, source, metric, scope, "
            "window_start, window_end, z_score, pct_change, {st:String} AS status, now() "
            "FROM rca.incidents FINAL WHERE incident_id = {inc:String}",
            {"st": status, "inc": self.incident_id})
        # root span: makes the trace a tree in HyperDX (steps parent to this) and
        # carries the verdict + headline + total wall-clock of the whole investigation
        self.otlp.send_span(
            self.trace_hex, f"investigate {self.incident_id}",
            self.t0_ns, int(time.time() * 1e9),
            {
                "rca.incident_id": self.incident_id,
                "rca.final_status": status,
                "rca.headline": headline,
                "rca.steps": self.step_no,
                **self.ctx,
            },
            span_id=self.root_span)


def timed(fn):
    """Helper: run fn(), return (result, duration_ms) for step logging."""
    t0 = time.monotonic()
    out = fn()
    return out, int((time.monotonic() - t0) * 1000)
