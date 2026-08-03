"""Lane C: turn an EvidenceBundle into prose. LLM narrates; it never computes.

Feed the bundle, ask for <= config.narrator.max_sentences sentences covering: the headline move,
the localized segment, the responsible factor, and the ruled-out list. Then run the guardrail.
"""
from __future__ import annotations

import boto3

from config import BEDROCK, config
from models import EvidenceBundle
from narrator.guardrail import verify

SYSTEM = (
    "You are a data analyst writing a diagnosis. Use ONLY numbers present in the provided "
    "evidence bundle. Never compute, infer, or round into a new figure. State the headline move, "
    "the localized segment, the responsible factor, and what was checked and ruled out.\n"
    "\n"
    "Reproduce every number EXACTLY as it appears in the bundle. Do not add currency symbols "
    "($, £, €), do not add scale suffixes (K, M, B, million, billion), and do not add units of "
    "any kind. The bundle stores bare numbers; writing 18.33 as '$18.33M' overstates it by a "
    "million and reads as a fabricated figure. If a value is 18.33, write 18.33.\n"
    "\n"
    "If the bundle has no localized segment or no ruled-out entries, say plainly that "
    "localization did not complete. Do not describe a move as significant when the bundle's "
    "pct_delta is small; report the number and let it speak."
)

# Only the evidence fields the narrator may draw from — keeps the prompt tight.
_EVIDENCE = {"metric", "anomaly", "factor_decomposition", "drilldown", "localized_segment", "ruled_out"}


def narrate(bundle: EvidenceBundle) -> EvidenceBundle:
    # TODO(Lane C): on guardrail failure, re-prompt or strip the offending number.
    prose = _call_llm(bundle)
    bundle.narrative = prose
    bundle.narrative_verification = verify(bundle, prose)
    return bundle


def _call_llm(bundle: EvidenceBundle) -> str:
    cfg = config()["narrator"]
    client = boto3.client("bedrock-runtime", region_name=BEDROCK["region"])
    prompt = (
        f"{SYSTEM}\n\nWrite at most {cfg['max_sentences']} sentences.\n\n"
        f"Evidence bundle (JSON):\n{bundle.model_dump_json(include=_EVIDENCE)}"
    )
    resp = client.converse(
        modelId=BEDROCK["model_id"],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": cfg["temperature"]},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


# ---- general conversational reply ------------------------------------------

CHAT_SYSTEM = (
    "You are the RCA Analyst assistant, a concise and helpful data-analysis copilot embedded in "
    "an anomaly root-cause dashboard. Answer conversationally, like a normal AI assistant. "
    "If the user asks about the investigation currently on screen, use the CONTEXT below; "
    "otherwise just answer helpfully. Keep replies brief unless asked to elaborate. Never invent "
    "metric figures — if asked for a number that is not in the CONTEXT, say you do not have it."
)


def general_reply(messages: list[tuple[str, str]], context_json: str | None = None) -> str:
    """A normal conversational LLM answer, used for anything that is not an explicit replay/explain
    or a fully-specified investigate request. `messages` is [(role, text), ...] ending with the
    user's latest turn; `context_json` is the on-screen bundle as JSON (optional context)."""
    system = CHAT_SYSTEM
    if context_json:
        system += "\n\nCONTEXT — the anomaly currently on the dashboard (JSON):\n" + context_json
    conv = [
        {"role": "assistant" if role == "assistant" else "user", "content": [{"text": text}]}
        for role, text in messages
        if text
    ]
    # Bedrock's converse requires the turn list to start with a user message.
    while conv and conv[0]["role"] != "user":
        conv.pop(0)
    if not conv:
        conv = [{"role": "user", "content": [{"text": "Hello"}]}]
    client = boto3.client("bedrock-runtime", region_name=BEDROCK["region"])
    resp = client.converse(
        modelId=BEDROCK["model_id"],
        system=[{"text": system}],
        messages=conv,
        inferenceConfig={"maxTokens": 600, "temperature": 0.4},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()
