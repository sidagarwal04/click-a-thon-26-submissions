"""
llm_judge.py
------------
LLM-as-judge for the parts of an answer that genuinely are subjective.

Correctness is NOT judged here — correctness.py settles that against ClickHouse.
Asking a model to grade a number it cannot verify produces confident noise. The
judge scores only what no query can settle: whether the answer is grounded in
what it actually retrieved, whether it is tight, whether it tells you anything
you can act on, and whether it reads clearly.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from langfuse_client import call_judge

_JUDGE_SYSTEM = """\
You evaluate answers from a streaming-analytics assistant that queries a
database before responding. Score the OUTPUT 0-10 on each criterion.

groundedness  Does it answer from retrieved data rather than hedging or
              generalising? Penalise vague answers with no specifics. Do NOT
              try to verify the numbers themselves — that is checked elsewhere.
conciseness   Tight and free of padding, restated questions, and preamble.
actionability Does it leave the reader knowing what to do or watch next?
clarity       Plain language, readable by someone who is not an engineer.

Respond ONLY with a JSON object, no prose, no markdown fences:
{"groundedness":<0-10>,"conciseness":<0-10>,"actionability":<0-10>,"clarity":<0-10>,"reasoning":"<one short sentence>"}
"""

_JUDGE_USER = """\
QUESTION:
{input_text}

ANSWER:
{output_text}

Word count: {wc}
"""

_AXES = ("groundedness", "conciseness", "actionability", "clarity")


def _score(input_text, output_text: str) -> dict:
    user = _JUDGE_USER.format(
        input_text=str(input_text)[:2000],
        output_text=output_text,
        wc=len(str(output_text).split()),
    )
    raw = (call_judge(user, system=_JUDGE_SYSTEM, max_tokens=400) or "").strip()

    for candidate in (
        raw,
        re.sub(r"```json|```", "", raw).strip(),
    ):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    print(f"[judge] unparseable response: {raw[:180]!r}")
    return {}


def llm_judge_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    if not output:
        return [{"name": "error", "value": 0.0, "comment": "empty output"}]

    scores = _score(input, output)
    reasoning = scores.get("reasoning", "")
    evals = [
        {"name": axis, "value": float(scores[axis]) / 10.0, "comment": reasoning}
        for axis in _AXES if axis in scores
    ]
    return evals or [{
        "name": "judge_parse_failed", "value": 0.0,
        "comment": "judge did not return valid JSON",
    }]