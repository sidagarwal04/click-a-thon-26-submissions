"""
The actual LLM agent version of hyperdx_rca_handler.py -- built on LangChain.

hyperdx_rca_handler.py is fully deterministic: fixed SQL (rca_dimscan ->
rca_segments), hardcoded Python logic, no model call. This module is the
real thing -- a LangChain tool-calling agent (ChatAnthropic, Claude Haiku
4.5) with live SQL tool access against inmobi_unseen. It reasons through
the drill-down itself (which dimension, which segment, rate vs mix) rather
than following a fixed script.

Optimized for latency: the alert's numbers (window, metric, severity,
observed/baseline, revenue impact) are fetched deterministically in Python
*before* the agent is invoked, so the agent never has to query
alerts_live/v_factors_1h itself -- its only job is the two-query drill-down
(rca_dimscan -> rca_segments) plus the narrative. The system prompt is a
short, protocol-only spec (exact SQL templates, exact column names, exact
dimension list) instead of the full human-facing schema doc, so per-turn
prompt processing stays small. Target: ~2-3s for the dimension-pick call,
~8-10s end to end for a metric with a drill-down; a single fast call with no
tool use at all for 'requests' (no rate/mix split exists for it).

HyperDX alert -> webhook -> this endpoint -> LangChain AgentExecutor
investigates via the run_sql tool -> ends with a fenced ```json block ->
parsed and written to rca_results (source='llm_agent') -> traced to
Langfuse via LangChain's native CallbackHandler (full tool-call tree, not
just a single span).

Run: CH_HOST=... CH_PORT=8443 CH_SECURE=true CH_DATABASE=inmobi_unseen \
     CH_USER=default CH_PASSWORD=... ANTHROPIC_API_KEY=... \
     LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... LANGFUSE_HOST=http://localhost:3000 \
     python -m agent.llm_rca_agent
Listens on 0.0.0.0:9203.
"""

import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from .client import get_client

app = Flask(__name__)

MODEL = "claude-haiku-4-5"

# Below this, a dimension's move isn't concentrated enough to name as "the"
# driver -- same floor hyperdx_rca_handler.py uses.
CONCENTRATION_MIN = 1.5

# Metrics rca_dimscan/rca_segments actually support (revenue maps to rpr;
# requests has no rate/mix split -- that's rca_volume, not modeled here, so
# it gets a tool-free narrate-only path below).
_DRILLABLE = ("fill_rate", "render_rate", "ecpm", "rpr")

# Same 30% floor hyperdx_rca_handler.py uses: rca_dimscan/rca_segments pool
# against only 1-4 prior same-table days early in this 5-day window, so
# concentration can clear the 1.5 threshold on noise alone (verified: Jul 7
# ecpm's `country` scored concentration 6.47 but its top segment's
# total_effect was ~3% of that hour's actual deviation). The agent applies
# this itself in Step 2 below rather than Python overriding its answer.
ATTRIBUTION_MIN_SHARE = 0.3

SYSTEM_PROMPT = """You are an automated revenue root-cause narrator for a mobile ad exchange
(ClickHouse database `inmobi_unseen`). You are invoked once per already-confirmed alert -- the
window, metric, severity, observed/baseline, and revenue impact are handed to you in the user
message. Do NOT query alerts_live or v_factors_1h yourself; that work is already done.

Revenue = Requests x Fill_rate x Render_rate x eCPM / 1000. Contributions are LMDI-decomposed
(already computed for you as revenue_impact_usd).

## Your ONLY job: two tool calls, then narrate

**Step 1 -- which dimension?** Call `run_sql` with EXACTLY (fill in target_day/dimscan_metric
from the payload you were given):
`SELECT dimension, concentration, worst_seg_x FROM rca_dimscan(target_day = '<target_day>', metric = '<dimscan_metric>') ORDER BY concentration DESC LIMIT 3`

Read `concentration` on the top row:
- < 1.5 -> no dimension explains it. Stop here (skip step 2), report an empty top_dimension/top_segment.
- >= 1.5 -> proceed to step 2 with that row's `dimension`.

**Step 2 -- which segment?** Call `run_sql` with EXACTLY (substitute the winning dimension):
`SELECT segment, baseline, observed, rate_effect, mix_effect, total_effect FROM rca_segments(target_day = '<target_day>', metric = '<dimscan_metric>', dim = '<dimension>') ORDER BY abs(total_effect) DESC LIMIT 1`

`rate_effect` dominant (|rate_effect| >= |mix_effect|) = a real fault in that segment.
`mix_effect` dominant = traffic mix shifted between segments, nothing in any one segment broke.
They sum to the metric's delta -- always say which one it is.

**Check the attribution is real before naming it.** Compute `expected_delta = baseline *
deviation_pct / 100` from the numbers you were given. If `abs(total_effect) / abs(expected_delta)
< 0.3` for the top segment, its effect is too small to actually explain the deviation --
`rca_dimscan`/`rca_segments` only pool against 1-4 prior same-table days this early in the
5-day window, so `concentration` clearing 1.5 can happen on noise alone. In that case do NOT
name the segment: set `top_dimension`/`top_segment` to empty strings, set
`attribution_reliable` to false, and say in the narrative that the deviation is real but no
segment reliably explains it (thin same-table baseline, not a data bug).

**Column names -- do not invent others.** `rca_dimscan` returns exactly `dimension`,
`concentration`, `worst_seg_x`. `rca_segments` returns exactly `segment`, `baseline`,
`observed`, `rate_effect`, `mix_effect`, `total_effect` -- never `dim_value` or `value`.

`dim` must be exactly one of: ad_format, category, publisher_tier, region, country,
device_model, os_version, vertical, campaign_type.

**Trap:** `vertical`/`campaign_type` only ever explain `ecpm`/`render_rate` (advertiser
attributes exist only on filled requests) -- they'll read concentration ~= 1 for other
metrics; don't report them as the driver there.

Run exactly these queries, in this order, once each. Do not run extra exploratory queries and
do not repeat a query that already succeeded.

## Final answer

End your final response with exactly one fenced ```json code block, no other keys, no markdown
inside it. Echo window_start/window_end/metric/severity back verbatim from what you were given:

```json
{
  "window_start": "<echoed>",
  "window_end": "<echoed>",
  "metric": "<echoed>",
  "severity": "<echoed>",
  "top_dimension": "<dimension, or empty string>",
  "top_segment": "<segment, or empty string>",
  "rate_or_mix": "<'rate', 'mix', or empty string>",
  "attribution_reliable": <true, or false if you discarded the attribution per the check above>,
  "narrative": "<2-3 sentence quantified conclusion>"
}
```
"""

NO_DRILLDOWN_SUFFIX = """

This particular request has NO dimension drill-down available (no rate/mix split exists for
`requests`). Skip both tool calls entirely -- do not call run_sql at all -- and go straight to
the final ```json block using only the numbers you were given, with top_dimension/top_segment/
rate_or_mix all empty strings and attribution_reliable true (there's nothing to be unreliable
about -- there was no drill-down attempted).
"""


_langfuse_ready = False


def get_langfuse_handler():
    """LangChain's native Langfuse integration -- traces the whole agent run
    (LLM calls + every tool call) as one tree, not just a single span.
    None if LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set (soft-fail, same as
    the deterministic handler)."""
    global _langfuse_ready
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return None
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    if not _langfuse_ready:
        Langfuse()  # registers itself as the default client from env vars; CallbackHandler() attaches to it
        _langfuse_ready = True
    return CallbackHandler()


_queries_this_request = []


@tool
def run_sql(query: str) -> str:
    """Run a read-only SQL SELECT query against the inmobi_unseen ClickHouse database
    and get the results back as JSON. Only SELECT statements are allowed. Results are
    capped at 50 rows. Use this only for the rca_dimscan/rca_segments calls described
    in your instructions -- the alert numbers are already given to you."""
    stripped = query.strip()
    if not stripped.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed."})
    _queries_this_request.append(query)
    try:
        client = get_client()
        result = client.query(query)
        rows = [dict(zip(result.column_names, row)) for row in result.result_rows[:50]]
        return json.dumps(rows, default=str)
    except Exception as e:  # noqa: BLE001 -- surface the DB error back to the model, don't crash the request
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# cache_control on the system message: Anthropic caches the (now-small, but
# still worth it under bursty alert traffic) prompt for ~5 min so back-to-back
# investigate() calls skip re-processing it.
_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

_llm = ChatAnthropic(model=MODEL, max_tokens=1024)
_agent = create_tool_calling_agent(_llm, [run_sql], _prompt)
_executor = AgentExecutor(agent=_agent, tools=[run_sql], max_iterations=4, return_intermediate_steps=True)


def _extract_json_block(text: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _fetch_alert_row(client, start: datetime, end: datetime) -> dict:
    """The single worst-z metric flagged in this window -- deterministic, no LLM.
    Mirrors hyperdx_rca_handler.py's query but LIMIT 1: this agent narrates one
    metric per invocation, matching what a single HyperDX alert fire represents."""
    rows = client.query(
        "SELECT window_hour, metric, observed, baseline, deviation_pct, robust_z, severity, sample_requests "
        "FROM alerts_live WHERE window_hour >= %(start)s AND window_hour < %(end)s "
        "ORDER BY abs(robust_z) DESC LIMIT 1",
        parameters={"start": start, "end": end},
    ).result_rows
    if not rows:
        return {}
    window_hour, metric, observed, baseline, deviation_pct, robust_z, severity, sample_requests = rows[0]
    return {
        "window_hour": window_hour, "metric": metric, "observed": float(observed),
        "baseline": float(baseline), "deviation_pct": float(deviation_pct),
        "robust_z": float(robust_z), "severity": severity, "sample_requests": int(sample_requests),
    }


def _is_confirmed(client, window_hour, metric: str) -> bool:
    """alerts_live_confirmed = alerts_live rows whose (metric, incident_id) run is
    >=2 consecutive hours, same persistence rule v_incidents_live uses. A window
    that isn't in it never repeated -- statistical noise, not a real incident."""
    rows = client.query(
        "SELECT 1 FROM alerts_live_confirmed WHERE window_hour = %(hour)s AND metric = %(metric)s LIMIT 1",
        parameters={"hour": window_hour, "metric": metric},
    ).result_rows
    return bool(rows)


def _revenue_impact(client, window_hour, flagged_metric: str) -> float:
    """Same LMDI calc as hyperdx_rca_handler.py's _revenue_impact -- duplicated (not
    imported) so this module stays independent of the deterministic handler's Flask app."""
    if flagged_metric not in ("requests", "fill_rate", "render_rate", "ecpm", "revenue"):
        return 0.0

    rows = client.query(
        "SELECT req, fill_rate, render_rate, ecpm, rev FROM v_factors_1h WHERE hour = %(hour)s",
        parameters={"hour": window_hour},
    ).result_rows
    if not rows:
        return 0.0
    req, fill_rate, render_rate, ecpm, rev = (float(v) for v in rows[0])

    base_rows = client.query(
        "SELECT metric, baseline FROM baseline_1h "
        "WHERE dow = toDayOfWeek(toDateTime(%(hour)s)) AND hod = toHour(toDateTime(%(hour)s)) "
        "AND metric IN ('requests', 'revenue', 'fill_rate', 'render_rate', 'ecpm')",
        parameters={"hour": window_hour},
    ).result_rows
    baseline = {m: float(b) for m, b in base_rows}
    if not all(k in baseline for k in ("requests", "revenue", "fill_rate", "render_rate", "ecpm")):
        return 0.0
    req_b, rev_b = baseline["requests"], baseline["revenue"]
    if rev <= 0 or rev_b <= 0 or req <= 0 or req_b <= 0:
        return 0.0

    L = rev_b if abs(rev - rev_b) < 1e-9 else (rev - rev_b) / math.log(rev / rev_b)
    contributions = {
        "requests": L * math.log(req / req_b) if req_b else 0.0,
        "fill_rate": L * math.log(fill_rate / baseline["fill_rate"]) if baseline["fill_rate"] else 0.0,
        "render_rate": L * math.log(render_rate / baseline["render_rate"]) if baseline["render_rate"] else 0.0,
        "ecpm": L * math.log(ecpm / baseline["ecpm"]) if baseline["ecpm"] else 0.0,
        "revenue": rev - rev_b,
    }
    return round(contributions.get(flagged_metric, 0.0), 2)


def investigate(start: datetime, end: datetime) -> dict:
    _queries_this_request.clear()
    t0 = time.monotonic()

    client = get_client()
    alert = _fetch_alert_row(client, start, end)
    if not alert:
        return {"raw_response": "", "structured": {}, "sql_queries": [], "model": MODEL,
                "elapsed_seconds": round(time.monotonic() - t0, 2), "note": "no alert in this window"}

    if not _is_confirmed(client, alert["window_hour"], alert["metric"]):
        # Isolated single-hour blip, never repeated -- close it out as a false
        # positive without spending an LLM call on it at all.
        window_hour = alert["window_hour"].replace(tzinfo=timezone.utc)
        window_end = window_hour + timedelta(hours=1)
        narrative = (f"{alert['metric']} moved {abs(alert['deviation_pct']):.1f}% "
                     f"(z={alert['robust_z']:.1f}) in this single hour only and did not persist -- "
                     f"statistical noise under alerts_live_confirmed's breach_hours>=2 rule, not a real "
                     f"incident. No drill-down performed.")
        structured = {
            "window_start": window_hour.isoformat(), "window_end": window_end.isoformat(),
            "metric": alert["metric"], "severity": alert["severity"],
            "top_dimension": "", "top_segment": "", "rate_or_mix": "",
            "attribution_reliable": True, "narrative": narrative,
        }
        return {"raw_response": narrative, "structured": structured, "sql_queries": [], "model": MODEL,
                "elapsed_seconds": round(time.monotonic() - t0, 2), "is_false_positive": True}

    window_hour = alert["window_hour"].replace(tzinfo=timezone.utc)
    window_end = window_hour + timedelta(hours=1)
    revenue_impact_usd = _revenue_impact(client, window_hour, alert["metric"])
    dimscan_metric = "rpr" if alert["metric"] == "revenue" else alert["metric"]
    drillable = dimscan_metric in _DRILLABLE

    payload = {
        "window_start": window_hour.isoformat(), "window_end": window_end.isoformat(),
        "metric": alert["metric"], "severity": alert["severity"],
        "observed": alert["observed"], "baseline": alert["baseline"],
        "deviation_pct": alert["deviation_pct"], "robust_z": alert["robust_z"],
        "revenue_impact_usd": revenue_impact_usd,
        "target_day": window_hour.strftime("%Y-%m-%d"), "dimscan_metric": dimscan_metric,
    }
    user_message = "Alert already confirmed. Numbers:\n" + json.dumps(payload)
    if not drillable:
        user_message += NO_DRILLDOWN_SUFFIX

    handler = get_langfuse_handler()
    config = {"callbacks": [handler]} if handler else {}

    result = _executor.invoke({"input": user_message}, config=config)
    final_text = result["output"]
    if isinstance(final_text, list):  # ChatAnthropic can return content-block list instead of a bare string
        final_text = "".join(b.get("text", "") for b in final_text if isinstance(b, dict))

    structured = _extract_json_block(final_text)
    elapsed = round(time.monotonic() - t0, 2)
    return {
        "raw_response": final_text,
        "structured": structured,
        "sql_queries": list(_queries_this_request),
        "model": MODEL,
        "elapsed_seconds": elapsed,
    }


def store(evidence: dict) -> None:
    structured = evidence.get("structured") or {}
    if not structured.get("window_start"):
        return  # nothing structured came back -- don't write a garbage row

    client = get_client()
    window_start = datetime.fromisoformat(structured["window_start"].replace("Z", "+00:00"))
    window_end = datetime.fromisoformat(structured["window_end"].replace("Z", "+00:00"))
    is_false_positive = bool(evidence.get("is_false_positive", False))
    attribution_reliable = bool(structured.get("attribution_reliable", True))

    client.insert(
        "rca_results",
        [[
            window_start, window_end, structured.get("metric", ""), structured.get("severity", ""),
            0.0, 0.0, 0.0, 0.0, 0.0,  # observed/baseline/deviation_pct/robust_z/revenue_impact_usd -- the LLM path doesn't recompute these; they live in alerts_live
            structured.get("top_dimension", ""), 0.0, structured.get("top_segment", ""),
            0.0, 0.0, 0.0, 0.0,
            structured.get("narrative", ""), json.dumps(evidence, default=str),
            "llm_agent", MODEL, json.dumps(evidence.get("sql_queries", [])),
            int(is_false_positive), int(attribution_reliable),
        ]],
        column_names=["window_start", "window_end", "metric", "severity", "observed", "baseline",
                      "deviation_pct", "robust_z", "revenue_impact_usd", "top_dimension", "top_concentration",
                      "top_segment", "segment_baseline", "segment_observed", "rate_effect", "mix_effect",
                      "narrative", "evidence_json", "source", "agent_model", "sql_queries",
                      "is_false_positive", "attribution_reliable"],
    )


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/hyperdx-hook", methods=["POST"])
def hyperdx_hook():
    data = request.get_json(force=True, silent=True) or {}
    start_ms, end_ms = data.get("startTime"), data.get("endTime")
    if start_ms is None or end_ms is None:
        return jsonify({"error": "startTime/endTime (epoch ms) required"}), 400

    start = datetime.fromtimestamp(int(start_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
    end = datetime.fromtimestamp(int(end_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)

    evidence = investigate(start, end)
    store(evidence)
    return jsonify(evidence), 200


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=9203, threads=4)
