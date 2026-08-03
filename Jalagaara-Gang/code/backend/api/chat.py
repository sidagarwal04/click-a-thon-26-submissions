"""JAL-82: conversational layer, in the OpenAI wire format.

LibreChat is one of the three blessed integrations and it talks to MODEL PROVIDERS, not custom
APIs: a custom endpoint calls {baseURL}/chat/completions with {model, messages[], stream} and
reads choices[0].message.content. Rather than build a translation layer, this endpoint returns
a valid chat completion with our own fields riding alongside. OpenAI clients ignore unknown
keys, so ONE endpoint serves both LibreChat and the dashboard.

Slot filling comes from the kangavault HaystackChatService pattern: collect what an
investigation needs across turns, and only act once it is complete. That removes the need for
the model to parse an entire request in one shot.

    "why did revenue drop?"  -> metric=revenue, window=?   -> ask for the window
    "the 23rd"               -> slots complete             -> investigate

Because LibreChat resends the whole message history every turn, slot filling needs no
server-side state machine - re-reading the transcript reconstructs it. Stored turns
(data.store) exist for clients that do NOT replay history, and for GET /chat/sessions.

Slot extraction here is deliberately deterministic (regex over the transcript) rather than an
LLM call. It is cheap, testable without a network, and cannot hallucinate a date that was
never mentioned.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

MODEL_NAME = "rca-analyst"

# Metric synonyms as a human would say them. Order matters: the most specific phrasing wins,
# so "revenue per request" is not swallowed by "revenue".
_METRIC_PATTERNS: list[tuple[str, str]] = [
    ("revenue per request", "rpr"),
    ("fill rate", "fill_rate"),
    ("fill-rate", "fill_rate"),
    ("fillrate", "fill_rate"),
    ("render rate", "render_rate"),
    ("click through", "ctr"),
    ("click-through", "ctr"),
    ("ctr", "ctr"),
    ("ecpm", "ecpm"),
    ("cpm", "ecpm"),
    ("impressions", "impressions"),
    ("requests", "requests"),
    ("traffic", "requests"),
    ("fills", "fills"),
    ("clicks", "clicks"),
    ("revenue", "revenue"),
]

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# "june 23", "jun 23-25", "23rd june", "2026-06-23"
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})"
    r"(?:\s*(?:-|to|through|until)\s*(\d{1,2}))?\b", re.I)
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
# Bare ordinal, only meaningful once a month is already known from context: "the 23rd"
_BARE_DAY = re.compile(r"\bthe\s+(\d{1,2})(?:st|nd|rd|th)\b", re.I)
# A month named on its own, e.g. "what happened in june". Only consulted when a bare ordinal
# is present, which keeps the unavoidable "may" (modal verb) collision harmless.
_BARE_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", re.I)

Intent = Literal["scan", "investigate", "followup", "greeting", "replay", "baseline"]
_GREETINGS = {"hi", "hey", "hello", "yo", "thanks", "thank you", "ok", "okay"}
_SCAN_HINTS = ("what's wrong", "whats wrong", "anything wrong", "any issues", "any incidents",
               "what happened", "show me incidents", "list incidents", "anomalies")
# "replay this anomaly end to end", "walk me through the incident", "explain the investigation".
# The demo flow: the dashboard shows an anomaly, the user asks the chat to replay it — the
# answer is rebuilt from the stored bundle, so no re-detection runs and no number is invented.
_REPLAY_HINTS = ("replay", "walk me through", "walk through", "end to end", "end-to-end",
                 "explain the investigation", "explain this investigation", "explain the anomaly",
                 "explain this anomaly", "explain the incident", "explain this incident",
                 "explain the drop", "explain this drop", "explain this",
                 "break it down", "break this down", "breakdown",
                 "recap", "step by step", "step-by-step",
                 "summarize the investigation", "summarise the investigation",
                 "summarize this investigation", "summarise this investigation",
                 "how was this investigated", "how did the investigation",
                 "how did you investigate", "how did you localize", "how did you localise",
                 "go through the investigation")
# "what were the normal values that day", "what's typical", "how does this compare to baseline".
# The anomaly bundle only knows ITS OWN window — answering this needs a different query (the
# surrounding days in `bundles`), which is exactly the case main._handle_chat routes separately.
_BASELINE_HINTS = ("normal value", "normal values", "on a normal day", "typical value",
                    "typical values", "usual value", "usual values", "baseline value",
                    "baseline values", "compare to normal", "compare to baseline",
                    "other days", "surrounding days", "how does this compare", "what's typical",
                    "whats typical", "what is typical")


# ---- OpenAI wire types -----------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str = ""


class ChatCompletionRequest(BaseModel):
    """The OpenAI request shape LibreChat sends. `model` is accepted and ignored - the
    narrator model is chosen server-side."""
    model: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    conversation_id: str | None = None
    user: str | None = None
    # Dashboard extension: the anomaly currently showcased. When set, "this anomaly" questions
    # (replay, follow-ups) resolve to THIS stored bundle instead of the latest one. OpenAI
    # clients (LibreChat) simply never send it.
    bundle_id: str | None = None

    def last_user_message(self) -> str:
        for message in reversed(self.messages):
            if message.role == "user":
                return message.content.strip()
        return ""

    def transcript(self) -> str:
        """All user turns oldest-first. Slots accumulate across the conversation, so
        'revenue' from turn 1 still applies when turn 3 says 'the 23rd'."""
        return "\n".join(m.content for m in self.messages if m.role == "user")


@dataclass
class Slots:
    metric: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    segment: dict[str, Any] | None = None

    @property
    def missing(self) -> list[str]:
        out = []
        if not self.metric:
            out.append("metric")
        if not self.window_start:
            out.append("window")
        return out

    @property
    def ready(self) -> bool:
        return not self.missing

    def as_dict(self, context_id: str) -> dict:
        window = None
        if self.window_start:
            window = f"{self.window_start:%Y-%m-%d}/{(self.window_end or self.window_start):%Y-%m-%d}"
        return {"metric": self.metric, "window": window,
                "segment": self.segment, "contextId": context_id}


# ---- slot extraction (pure) ------------------------------------------------

def extract_metric(text: str) -> str | None:
    lowered = text.lower()
    for phrase, metric in _METRIC_PATTERNS:
        if phrase in lowered:
            return metric
    return None


def _month_context(text: str) -> int | None:
    """Last month named anywhere in the transcript, so a bare 'the 23rd' resolves.

    Matches a bare month too ("what happened in june" ... "the 23rd"), not only a month
    attached to a day - that split across turns is the common case.
    """
    names = _BARE_MONTH.findall(text)
    if names:
        return _MONTHS[names[-1][:3].lower()]
    iso = _ISO.findall(text)
    return int(iso[-1][1]) if iso else None


def extract_window(text: str, default_year: int = 2026) -> tuple[datetime, datetime] | None:
    """Return [start, end) for the last date reference in the text.

    A single day yields a one-day window; a range like 'Jun 23-25' yields three days. The end
    is exclusive so it composes with the incident scanner's windows.
    """
    iso = _ISO.findall(text)
    if iso:
        year, month, day = (int(p) for p in iso[-1])
        start = datetime(year, month, day)
        return start, start + timedelta(days=1)

    md = _MONTH_DAY.findall(text)
    if md:
        name, first, last = md[-1]
        month = _MONTHS[name[:3].lower()]
        start = datetime(default_year, month, int(first))
        end = datetime(default_year, month, int(last)) + timedelta(days=1) if last else start + timedelta(days=1)
        return start, end

    dm = _DAY_MONTH.findall(text)
    if dm:
        day, name = dm[-1]
        start = datetime(default_year, _MONTHS[name[:3].lower()], int(day))
        return start, start + timedelta(days=1)

    bare = _BARE_DAY.findall(text)
    if bare:
        month = _month_context(text)
        if month:
            start = datetime(default_year, month, int(bare[-1]))
            return start, start + timedelta(days=1)
    return None


def fill_slots(request: ChatCompletionRequest) -> Slots:
    """Rebuild slots from the whole transcript, newest mention winning."""
    transcript = request.transcript()
    slots = Slots(metric=extract_metric(transcript))
    window = extract_window(transcript)
    if window:
        slots.window_start, slots.window_end = window
    return slots


def classify(request: ChatCompletionRequest, slots: Slots) -> Intent:
    message = request.last_user_message().lower().strip(" ?!.")
    if message in _GREETINGS:
        return "greeting"
    # Baseline/replay both outrank investigate: naming a metric ("normal fill rate values")
    # would otherwise satisfy the investigate slots and trigger a fresh, unwanted detection run.
    if any(hint in message for hint in _BASELINE_HINTS):
        return "baseline"
    if any(hint in message for hint in _REPLAY_HINTS):
        return "replay"
    if any(hint in message for hint in _SCAN_HINTS):
        return "scan"
    return "investigate" if slots.ready else "followup"


# ---- conversation title (LibreChat calls the model to name the thread) -----

# LibreChat generates a title via a separate completion whose prompt embeds the transcript
# and instructs the model to write a title. Genuine investigation questions never contain the
# word "title", so this pairing is a version-robust signal. Handling it here keeps title prompts
# out of the slot-filler AND out of Langfuse investigation traces.
_TITLE_CUES = ("concise", "generate a title", "summar", "conversation that",
               "few words", "language of the", "title:", "short title")


def is_title_request(request: ChatCompletionRequest) -> bool:
    blob = " ".join(m.content for m in request.messages).lower()
    return "title" in blob and any(cue in blob for cue in _TITLE_CUES)


def make_title(request: ChatCompletionRequest) -> str:
    """A short deterministic title from whatever the transcript reveals - no LLM call."""
    slots = fill_slots(request)
    if slots.metric and slots.window_start:
        start = slots.window_start
        return f"{slots.metric.replace('_', ' ').title()} - {start:%b} {start.day}"
    if slots.metric:
        return f"{slots.metric.replace('_', ' ').title()} investigation"
    first = request.last_user_message() or "RCA investigation"
    return first[:40].strip()


# ---- response assembly -----------------------------------------------------

def completion(
    content: str,
    *,
    context_id: str,
    slots: Slots,
    investigation: dict | None = None,
    verification: dict | None = None,
    plot_kind: str | None = None,
    plot_data: list | None = None,
) -> dict:
    """A valid OpenAI chat completion, with our fields alongside.

    LibreChat reads choices[0].message.content. The dashboard reads `investigation` and
    `template`. Neither needs to know about the other.
    """
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        # --- extensions, ignored by OpenAI clients ---
        "contextId": context_id,
        "template": slots.as_dict(context_id),
        "isReadyForInvestigation": slots.ready,
        "missingFields": slots.missing,
        "investigation": investigation,
        "verification": verification,
        "isPlottable": plot_data is not None,
        "plotKind": plot_kind,
        "plotData": plot_data or [],
    }


def ask_for_missing(slots: Slots, incident_hint: str = "") -> str:
    """Prompt for whichever slot is absent. This reply becomes an assistant turn in
    LibreChat, and the user's answer arrives as the next user message."""
    if "metric" in slots.missing and "window" in slots.missing:
        return ("Which metric and time period should I look at? I can investigate revenue, "
                "requests, fill rate, render rate, eCPM or CTR." + incident_hint)
    if "metric" in slots.missing:
        return ("Which metric? I can investigate revenue, requests, fill rate, render rate, "
                "eCPM or CTR.")
    return "Which time period should I investigate?" + incident_hint
