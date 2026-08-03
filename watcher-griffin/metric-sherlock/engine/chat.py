"""Follow-up chat, grounded strictly in one investigation's already-computed
evidence bundle -- the PROBLEM_STATEMENT.md bonus ("optionally ask a
follow-up question in chat"). Same guardrail as engine/narrator.py: this
never runs a new ClickHouse query or invents a number. If the evidence
bundle doesn't cover what's asked, it says so explicitly instead of
guessing -- "no bluffing, only real traces" per the user's own instruction.
"""

import json
from dataclasses import dataclass
from typing import Optional

from engine.llm import get_provider

SYSTEM_PROMPT = """You are answering follow-up questions about ONE already-completed root-cause investigation.

You will be given: the full evidence JSON that investigation produced (metrics, factor decomposition, ranked \
segments, ruled-out checks, and the narration already given), followed by the conversation so far.

Hard rules, non-negotiable (same as the original narration):
1. Answer ONLY using numbers and facts present in the evidence JSON. Never compute a new number, never query \
new data, never estimate or invent something not already there. Do not add, subtract, average or convert \
figures -- if the number the question asks for is not already in the evidence, it does not exist for you.
2. If the question asks about something the evidence bundle doesn't cover (a different metric, a different \
time window, a segment that isn't in drilldown_levels/ruled_out), say plainly that this investigation's \
evidence doesn't cover that, and suggest running a new investigation for it. Do not guess. Refusing is a \
correct answer and is always better than an approximate one.
3. Keep answers short (1-3 sentences). Lead with what happened and why, in words a non-technical reader would \
say out loud -- never surface internal analysis vocabulary as the explanation itself (no "sibling \
values/entities", no "breadth", no raw rollup/step names, no bare thresholds standing in for meaning). \
Translate them into plain language, e.g. "only 4 of 111 sibling values moved, breadth 0.036" becomes "only a \
handful of similar apps moved, well within normal variation".
4. Still cite the specific dimension/value/number from the evidence, and whenever you state a number, name \
the `source_step` it came from, exactly as that field appears in the evidence -- for example "per the \
`rank:hourly_by_region:current` query". Place this citation as a short trailing clause AFTER the \
plain-language claim, not interleaved mid-sentence -- it's supporting detail for a reader who wants to \
re-run the figure, not the subject of the sentence. If a number you want to cite has no source_step in the \
evidence, do not use that number.

Output only your answer text, nothing else.
"""


@dataclass
class ChatReply:
    reply: Optional[str]
    available: bool
    provider: str
    error: Optional[str] = None


def ask(evidence_json: dict, history: list, question: str) -> ChatReply:
    """`history` is a list of {"role": "user"|"assistant", "content": str},
    already-persisted prior turns for this subject (empty for the first question).

    Wrapped in a real-time Langfuse generation span, for the same reason
    engine/narrator.py is: this is an LLM call whose latency and output a judge must be
    able to open and read. It previously ran bare, which made the one INTERACTIVE
    surface in the system the only one that left no trace. The caller supplies the root
    (tracing.traced_chat) because a follow-up arrives on its own HTTP request, long
    after the investigation's span closed.
    """
    from engine.config import settings
    from engine.tracing import traced_generation

    provider_name = settings.llm_provider.value
    span_input = {"question": question, "history_turns": len(history)}
    with traced_generation("chat", provider_name, span_input) as span:
        try:
            provider = get_provider(settings)
            transcript = "\n".join(f"{h['role']}: {h['content']}" for h in history)
            user_content = (
                f"EVIDENCE:\n{json.dumps(evidence_json, default=str)}\n\n"
                f"CONVERSATION SO FAR:\n{transcript}\n\n"
                f"NEW QUESTION:\n{question}"
            )
            text = provider.generate(SYSTEM_PROMPT, user_content)
            if span is not None:
                span.update(output=text)
            return ChatReply(reply=text, available=True, provider=provider_name)
        except Exception as e:
            # Degrade, never fabricate -- and record WHY on the span, so an unavailable
            # narration is a visible failure in the trace rather than a silent absence.
            if span is not None:
                span.update(output=None, level="ERROR", status_message=str(e)[:500])
            return ChatReply(reply=None, available=False, provider=provider_name, error=str(e))
