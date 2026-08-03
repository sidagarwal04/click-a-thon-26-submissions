"""LLM narration for the Drill-down table — Claude only phrases numbers that
are already in the JSON payload the frontend rendered; it never queries
ClickHouse or invents a figure. If ANTHROPIC_API_KEY isn't set, callers get
None back and fall back to no summary rather than a fake one.
"""
import json
import os

import anthropic
from langfuse import get_client as get_langfuse_client

_client = None
_client_checked = False


def _get_client():
    global _client, _client_checked
    if not _client_checked:
        _client_checked = True
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = (
    "You narrate ad-tech anomaly data for a dashboard. You are given a JSON array of "
    "segments within one breakdown dimension (e.g. device models, countries) during a "
    "flagged anomalous hour: each segment's actual revenue, its expected revenue for "
    "that same hour-of-week slot, the dollar delta, what share of the dimension's total "
    "delta it represents, its fill rate, and its eCPM.\n\n"
    "Write a short summary (2-3 sentences, plain English) of which segment(s) are most "
    "responsible for the deviation and by how much.\n\n"
    "STRICT RULES:\n"
    "- Use ONLY the numbers present in the JSON. Never invent, estimate, or round to a "
    "different figure than given.\n"
    "- Never speculate about WHY a segment moved (a device release, an outage, a market "
    "event, etc.) unless that reason is literally present in the JSON — it isn't, so "
    "don't guess at causes, only describe the numbers.\n"
    "- No AI disclaimers, no hedging, no restating these instructions.\n"
    "- If no segment clearly stands out (deltas small or spread evenly), say so plainly "
    "instead of forcing a story."
)


def summarize_drilldown(dimension_name, rows):
    client = _get_client()
    if client is None:
        return None

    payload = {"dimension_name": dimension_name, "segments": rows}
    user_content = f"Here is the data:\n\n{json.dumps(payload, default=str)}"
    model = "claude-haiku-4-5-20251001"

    with get_langfuse_client().start_as_current_observation(
        as_type="generation",
        name="summarize_drilldown",
        model=model,
        input={"system": SYSTEM_PROMPT, "user": user_content},
    ) as generation:
        message = client.messages.create(
            model=model,
            max_tokens=220,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = message.content[0].text.strip()
        generation.update(
            output=text,
            usage_details={
                "input": message.usage.input_tokens,
                "output": message.usage.output_tokens,
            },
        )
    return text


INCIDENT_SYSTEM_PROMPT = (
    "You narrate a full ad-tech revenue anomaly for a dashboard. You are given a JSON "
    "object with three parts, all for the same flagged hour:\n"
    "- detection: the actual vs. expected revenue for that hour-of-week slot, the percent "
    "deviation, and the robust z-score used to flag it.\n"
    "- factors: how much request volume, fill rate, and eCPM (price per 1,000 views) each "
    "moved vs. their typical value for this hour-of-week slot.\n"
    "- contribution: for EACH of up to 9 breakdown dimensions (country, device model, "
    "campaign type, etc.), the top segment's share of that one dimension's total delta "
    "(signed: positive means that segment rose, negative means it fell).\n\n"
    "Write a short narrative (4-6 sentences, plain English) covering: (1) what happened "
    "to revenue and how statistically unusual it was, (2) which factor (volume, fill "
    "rate, or price) was the primary driver, (3) whether any dimension's top segment is "
    "concentrated enough to call this 'localized' to that segment, or whether it looks "
    "broad-based across many segments.\n\n"
    "STRICT RULES:\n"
    "- Use ONLY the numbers present in the JSON. Never invent, estimate, or round to a "
    "different figure than given.\n"
    "- Never speculate about root causes (an outage, a market event, a policy change) "
    "unless that reason is literally present in the JSON — it isn't, so describe the "
    "numbers, don't invent a cause for them.\n"
    "- No AI disclaimers, no hedging, no restating these instructions.\n"
    "- Plain prose only: no markdown headers, no bullet points, no bold/italic markup. "
    "Keep it tight enough to finish within 6 sentences — never trail off mid-sentence."
)


def summarize_incident(detection, factors, contribution):
    client = _get_client()
    if client is None:
        return None

    payload = {"detection": detection, "factors": factors, "contribution": contribution}
    user_content = f"Here is the data:\n\n{json.dumps(payload, default=str)}"
    model = "claude-haiku-4-5-20251001"

    with get_langfuse_client().start_as_current_observation(
        as_type="generation",
        name="summarize_incident",
        model=model,
        input={"system": INCIDENT_SYSTEM_PROMPT, "user": user_content},
    ) as generation:
        message = client.messages.create(
            model=model,
            max_tokens=450,
            system=INCIDENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = message.content[0].text.strip()
        generation.update(
            output=text,
            usage_details={
                "input": message.usage.input_tokens,
                "output": message.usage.output_tokens,
            },
        )
    return text
