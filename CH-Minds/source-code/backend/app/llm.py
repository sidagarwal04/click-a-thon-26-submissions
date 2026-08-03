"""Narration and intent-parsing over already-computed structured data only -
never raw rows, never SQL generation. The LLM can't invent a number that
isn't already in the JSON handed to it."""
import json

from . import config, metrics

_NARRATE_BASE_PROMPT = (
    "You are a root-cause analyst narrating a pre-computed ad-metrics investigation. "
    "You are given ONLY structured, already-computed numbers as JSON - never invent, "
    "estimate, or round a number that isn't present in the input. Write 2-4 sentences: "
    "state what moved, by how much (cite the actual percentages/values given), and the "
    "specific segment or factor responsible. "
    "NEVER claim that anything was checked, investigated, considered, or ruled out "
    "unless it appears verbatim in the input's checked_and_ruled_out list. Do not "
    "mention factors that are not in the input at all (for example user engagement, "
    "content quality, seasonality, or market conditions) even to say they were "
    "excluded - if it is not in the input, it was not checked, and saying otherwise "
    "is a fabrication. If responsible_segment has a 'refined_by' field, that's a more "
    "specific intersection found within the segment (e.g. segment=country/IN "
    "refined_by=device_model/iPhone) - mention that tighter localization instead of "
    "just the outer segment. Plain language, no jargon, written for a product manager, "
    "not a database engineer."
)

_NARRATE_RULED_OUT_CLAUSE = (
    " The input includes a checked_and_ruled_out list; also state what was checked and "
    "came back normal, using only the entries in that list."
)

_NARRATE_COVERAGE_CLAUSE = (
    " The input includes a data_coverage_note: the day is only partially loaded and was "
    "compared over a restricted hour window. State this limitation explicitly in your "
    "answer so the reader does not mistake it for a full-day figure."
)

NARRATE_SYSTEM_PROMPT = _NARRATE_BASE_PROMPT + _NARRATE_RULED_OUT_CLAUSE

ASK_SYSTEM_PROMPT = (
    "You translate a free-text question into a structured lookup, for a system that answers "
    "questions about this ad-metrics dataset: revenue, fill rate, render rate, eCPM, CTR, "
    "and the app/device/geo/advertiser segments and days behind them. "
    'Respond with ONLY a JSON object, no markdown fences, no commentary: '
    '{"in_scope": true or false, '
    '"metric": one of [' + ", ".join(f'"{m}"' for m in metrics.HEADLINE_METRICS) + '] or null, '
    '"day": "YYYY-MM-DD" or null, '
    '"dimension": one of the listed dimension names or null, "value": the segment value '
    "as a string or null}. "
    "DEFAULT TO in_scope=true. Judge scope by TOPIC ONLY, never by grammar, spelling, "
    "punctuation, or how casually the question is phrased - a badly-worded or informal "
    "question about deviations, causes, percentages, or 'what happened' is still in scope. "
    "If the prompt below says an investigation is currently open, ANY vague or short "
    "follow-up ('why', 'what caused this', 'explain', 'give me an RCA', 'how much', 'what "
    "about X') is in scope and refers to that investigation, even with no metric/day/segment "
    "named explicitly - resolve it from context, don't refuse it. "
    "Only set in_scope to false when the question is CLEARLY about something with no "
    "plausible connection to ad-metrics or the open investigation at all - e.g. the weather, "
    "cooking, sports scores, personal advice, or an unrelated company/product. When (and "
    "only when) you set in_scope to false, also set metric/day/dimension/value to null. "
    "Use null for day if the question doesn't specify one."
)


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL, system_instruction=system_prompt)
    resp = model.generate_content(user_prompt)
    return resp.text


_PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
}


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    fn = _PROVIDERS.get(config.ACTIVE_LLM_PROVIDER)
    if fn is None:
        raise ValueError(
            f"Unknown ACTIVE_LLM_PROVIDER={config.ACTIVE_LLM_PROVIDER!r}, "
            f"expected one of {list(_PROVIDERS)}"
        )
    return fn(system_prompt, user_prompt)


def narrate(findings: dict) -> str:
    """System prompt is assembled from what findings actually contains -
    asking for a field the input can't supply is an instruction to
    hallucinate, which is what the old fixed prompt did on ask.py's path."""
    system_prompt = _NARRATE_BASE_PROMPT
    if findings.get("checked_and_ruled_out"):
        system_prompt += _NARRATE_RULED_OUT_CLAUSE
    if findings.get("data_coverage_note"):
        system_prompt += _NARRATE_COVERAGE_CLAUSE
    prompt = "Investigation findings (JSON):\n" + json.dumps(findings, default=str, indent=2)
    return _call_llm(system_prompt, prompt)


def parse_question(question: str, schema_hint: str) -> dict:
    prompt = f"{schema_hint}\n\nUser question: {question}"
    raw = _call_llm(ASK_SYSTEM_PROMPT, prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())
