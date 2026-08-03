"""Stage 5 — narration. The only stage that uses an LLM.

Everything before this computed the diagnosis. This stage writes it in English,
and nothing else: it receives aggregated, already-computed values and never sees
a raw event, so there is nothing for it to compute and nothing to get wrong.
Delete this stage entirely and the structured diagnosis is still complete and
correct — the prose is a rendering of it, not a source of it.

WHY THE NUMBER CHECK EXISTS
---------------------------
"Every number in the diagnosis must be reproducible from the data. A single
fabricated figure costs more than a missed anomaly." Restricting the model's
input makes fabrication unlikely; it does not make it impossible, and a
plausible wrong number is exactly the failure that survives review.

So after generation every numeric token in the prose is extracted and matched
against the payload the model was given. A figure that cannot be traced back is
flagged. This is a mechanical check on the output, not a promise about the
model, and it runs on every narration including the unseen incident.
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

MODEL = "claude-opus-5"

SYSTEM = """You are the narration layer of an automated root-cause analyst for \
ad-platform metrics.

Everything has already been computed by deterministic SQL against ClickHouse. \
Your only job is to write the finding in clear English for an on-call analyst.

Absolute rules:
- Use ONLY numbers present in the JSON you are given. Never estimate, derive, \
round differently, or invent a figure. If a number is not in the JSON, do not \
state it.
- Do not speculate about root cause beyond what the evidence shows. You may say \
what the pattern is consistent with, clearly marked as interpretation.
- The ruled-out evidence matters as much as the finding. Say what was checked \
and cleared, with its numbers.
- If no segment is responsible, say so plainly. "The drop was uniform across \
every dimension" is a real and useful finding, not a failure.
- The `signature` object describes the SHAPE of the change — whether it \
stepped within one hour or ramped, whether it landed on a day boundary, how \
long it lasted, whether it reversed, and which factors held steady throughout. \
Use it. Naming the factor and segment is a sharper "what"; the shape is where \
the "why" lives. A step change on a day boundary that reverses after a whole \
number of days did not degrade — it was switched, on a schedule. Say so, and \
say it is what the pattern is consistent with, not what caused it.
- `signature.rules_out` states what the evidence eliminates. Include it: what \
a pattern cannot be is as useful to an on-call engineer as what it might be.

Write 3 short paragraphs, no headings, no bullet points:
1. What moved, by how much, over what window.
2. Which factor and which segment — or that it was uniform and no segment is \
responsible — and the shape of the transition.
3. What was checked and ruled out, and what an on-call analyst should look at \
next."""


@dataclass
class Narration:
    text: str
    model: str
    payload: dict[str, Any]
    unverified_numbers: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def all_numbers_verified(self) -> bool:
        return not self.unverified_numbers


def build_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Reduce an Event to the computed values the narrator is allowed to see.

    Deliberately narrow. The per-hour findings, the raw rows and the SQL are all
    excluded — not to save tokens, but so that the model has nothing to compute
    from even if it tried.
    """
    dec = event["decomposition"]
    return {
        "window": {"start": event["start"], "end": event["end"], "hours": event["hours"]},
        "classification": event["classification"],
        "revenue_pct_change": round(event["revenue_pct_change"], 4),
        "primary_factor": event["primary_factor"],
        "factors": [
            {
                "factor": f["factor"],
                "actual": round(f["actual"], 4),
                "baseline": round(f["baseline"], 4),
                "pct_change": round(f["pct_change"], 4),
                "share_of_movement": round(f["contribution_share"], 4),
            }
            for f in dec["factors"]
        ],
        "responsible_segments": [
            {
                "dimension": v["dim_name"],
                "value": v["top_value"],
                "share_of_unexplained_movement": v["top_excess_share"],
                "share_of_incident": v["top_excess_of_total"],
                "evidence": v["reason"],
            }
            for v in event["responsible"]
        ],
        "ruled_out": [
            {"dimension": v["dim_name"], "verdict": v["verdict"], "evidence": v["reason"]}
            for v in event["ruled_out"]
        ],
        # The shape of the transition — measured, not inferred. This is what
        # lets the narration say something causal without leaving the evidence.
        "signature": event.get("signature"),
    }


_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _allowed_values(payload: Any, acc: set[float] | None = None) -> set[float]:
    """Every number the narrator may legitimately write.

    A value of 0.449 in the payload licenses "0.449", "44.9" and "45" in the
    prose, because a percentage is the same fact in different clothes and the
    model is told to write for humans. Rounded forms are admitted for the same
    reason. This is about catching invented figures, not policing formatting.
    """
    if acc is None:
        acc = set()
    if isinstance(payload, bool):
        return acc
    if isinstance(payload, (int, float)):
        v = float(payload)
        for candidate in (v, abs(v), v * 100, abs(v * 100)):
            acc.add(candidate)
            for places in (0, 1, 2, 3, 4):
                acc.add(round(candidate, places))
    elif isinstance(payload, dict):
        for value in payload.values():
            _allowed_values(value, acc)
    elif isinstance(payload, list):
        for item in payload:
            _allowed_values(item, acc)
    elif isinstance(payload, str):
        for match in _NUMBER.findall(payload):
            try:
                _allowed_values(float(match.replace(",", "")), acc)
            except ValueError:
                pass
    return acc


def verify_numbers(text: str, payload: dict[str, Any]) -> list[str]:
    """Return numeric tokens in `text` that cannot be traced to `payload`."""
    allowed = _allowed_values(payload)
    unverified: list[str] = []

    for token in _NUMBER.findall(text):
        cleaned = token.rstrip(".").replace(",", "")
        if not cleaned or cleaned == "-":
            continue
        try:
            value = float(cleaned)
        except ValueError:
            continue
        # Small integers are ordinals and counts ("3 paragraphs", "all 5 values"),
        # not claims about the data.
        if value.is_integer() and abs(value) <= 24:
            continue
        if any(abs(value - a) <= max(0.01, abs(a) * 0.001) for a in allowed):
            continue
        unverified.append(token)

    return unverified


def narrate(event: dict[str, Any], model: str = MODEL) -> Narration:
    """One LLM call over computed values. No tools, no data access."""
    import anthropic

    payload = build_payload(event)
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=model,
        max_tokens=1600,
        system=SYSTEM,
        # Narration is a rendering task, not a reasoning one — the analysis is
        # already done. Low effort keeps it fast and cheap without touching
        # quality, and thinking stays on rather than disabled.
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": (
                "Write the diagnosis for this incident. Use only these numbers:\n\n"
                + json.dumps(payload, indent=2)
            ),
        }],
    )

    text = "".join(block.text for block in response.content if block.type == "text").strip()

    return Narration(
        text=text,
        model=model,
        payload=payload,
        unverified_numbers=verify_numbers(text, payload),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
