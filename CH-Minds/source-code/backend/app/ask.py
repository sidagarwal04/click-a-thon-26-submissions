"""Chat: free-text question -> structured lookup -> narrated answer, reusing
investigate.py's query functions. Optional `context` (the open
investigation's metric/day/segment) resolves unqualified follow-ups."""
import json
from datetime import date
from typing import Optional

from . import db, investigate as investigate_module, llm, metrics, tracing

_SCHEMA_HINT = (
    "Metrics available: " + ", ".join(metrics.HEADLINE_METRICS) + ". "
    "Dimensions available: " + ", ".join(metrics.DIMENSIONS) + "."
)

_OUT_OF_SCOPE_ANSWER = (
    "That's outside what I can help with here. I can only answer questions about this "
    "ad-metrics investigation - revenue, fill rate, render rate, eCPM, CTR, and the "
    "segments/days behind them. Try asking about a metric, segment, or day instead."
)


def _latest_day(client) -> date:
    row = client.query("SELECT max(toDate(hour)) AS d FROM inmobi_rca.hourly_segment_metrics").result_rows
    return row[0][0]


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _build_schema_hint(context: Optional[dict]) -> str:
    if not context:
        return _SCHEMA_HINT
    parts = []
    if context.get("metric"):
        parts.append(f"metric={context['metric']}")
    if context.get("day"):
        parts.append(f"day={context['day']}")
    if context.get("dimension") and context.get("value"):
        parts.append(f"segment={context['dimension']}={context['value']}")
    if not parts:
        return _SCHEMA_HINT
    return (
        f"{_SCHEMA_HINT} The user currently has this investigation open: {', '.join(parts)}. "
        "If their question doesn't explicitly name a different metric, day, or segment, "
        "assume they mean this one - set that field to null in your response only if the "
        "question is clearly about something else. Because an investigation is open, treat "
        "any vague or casually-phrased follow-up (why, what caused this, explain, give me "
        "an RCA, how much, what's the deviation) as in scope and about this investigation - "
        "do not refuse these just because they don't spell out a metric/day/segment by name."
    )


def ask(question: str, context: Optional[dict] = None) -> dict:
    trace = tracing.start_trace(
        name="ask",
        input={"question": question, "context": context},
        metadata={"question": question, "context": context},
    )
    client = db.get_ro_client()
    admin = db.get_admin_client()

    schema_hint = _build_schema_hint(context)
    parsed = trace.run_span(
        "parse_question",
        lambda: llm.parse_question(question, schema_hint),
        input={"question": question, "context": context},
    )

    if not parsed.get("in_scope", True):
        answer = _OUT_OF_SCOPE_ANSWER
        trace_id = trace.finish(output={"answer": answer, "in_scope": False})
        admin.insert(
            "inmobi_rca.chat_queries",
            [[question, answer, json.dumps({"in_scope": False}), trace_id or ""]],
            column_names=["question", "answer_text", "cited_numbers", "langfuse_trace_id"],
        )
        return {"question": question, "answer": answer, "cited_numbers": {}, "langfuse_trace_id": trace_id}

    context = context or {}
    metric_name = parsed.get("metric") or context.get("metric")
    day = _as_date(parsed.get("day")) or _as_date(context.get("day")) or _latest_day(client)
    dim = parsed.get("dimension") or context.get("dimension")
    value = parsed.get("value") or context.get("value")

    if metric_name not in metrics.METRIC_EXPRESSIONS:
        result = {"note": f"Couldn't map that to a tracked metric (have: {', '.join(metrics.HEADLINE_METRICS)})."}
    elif dim and value:
        result = trace.run_span(
            "lookup_segment",
            lambda: investigate_module.segment_value_lookup(client, day, metric_name, dim, value),
            input={"metric": metric_name, "day": str(day), "dimension": dim, "value": value},
        )
    else:
        result = trace.run_span(
            "compute_deviation",
            lambda: investigate_module.compute_daily_deviation(client, day, metric_name) or {},
            input={"metric": metric_name, "day": str(day)},
        )

    answer = trace.run_span(
        "narrate_answer", lambda: llm.narrate({"question": question, **result}), input={"question": question, **result}
    )
    trace_id = trace.finish(output={"answer": answer, "cited_numbers": result})

    admin.insert(
        "inmobi_rca.chat_queries",
        [[question, answer, json.dumps(result, default=str), trace_id or ""]],
        column_names=["question", "answer_text", "cited_numbers", "langfuse_trace_id"],
    )

    return {"question": question, "answer": answer, "cited_numbers": result, "langfuse_trace_id": trace_id}
