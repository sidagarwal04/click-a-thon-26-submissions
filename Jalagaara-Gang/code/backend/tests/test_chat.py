"""JAL-82: slot filling, intent routing and the OpenAI wire format.

Slot extraction is deterministic on purpose, so it is fully testable here with no network.
The behaviour that carries the demo is accumulation across turns: "why did revenue drop?"
followed by "the 23rd" must produce a complete investigation.
"""
from datetime import datetime

import pytest

from api import chat as c


def req(*user_messages, **kwargs):
    """Build a request the way LibreChat does - full history replayed each turn."""
    messages = []
    for i, text in enumerate(user_messages):
        if i:
            messages.append(c.ChatMessage(role="assistant", content="Which time period?"))
        messages.append(c.ChatMessage(role="user", content=text))
    return c.ChatCompletionRequest(messages=messages, **kwargs)


# ---- metric extraction -----------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("why did revenue drop?", "revenue"),
    ("what happened to fill rate", "fill_rate"),
    ("fill-rate looks bad", "fill_rate"),
    ("eCPM fell", "ecpm"),
    ("CPM is down", "ecpm"),
    ("CTR dropped", "ctr"),
    ("click-through rate", "ctr"),
    ("traffic collapsed", "requests"),
    ("render rate", "render_rate"),
])
def test_extract_metric(text, expected):
    assert c.extract_metric(text) == expected


def test_specific_phrasing_wins_over_substring():
    """'revenue per request' must not be swallowed by 'revenue'."""
    assert c.extract_metric("revenue per request is down") == "rpr"


def test_unknown_metric_is_none():
    assert c.extract_metric("how are you") is None


# ---- window extraction -----------------------------------------------------

def test_iso_date():
    assert c.extract_window("look at 2026-06-23") == (datetime(2026, 6, 23), datetime(2026, 6, 24))


def test_month_day():
    assert c.extract_window("june 23") == (datetime(2026, 6, 23), datetime(2026, 6, 24))


def test_month_day_range():
    """'Jun 23-25' is three days, end exclusive."""
    assert c.extract_window("jun 23-25") == (datetime(2026, 6, 23), datetime(2026, 6, 26))


def test_range_with_word_separator():
    assert c.extract_window("june 28 to 30") == (datetime(2026, 6, 28), datetime(2026, 7, 1))


def test_day_then_month():
    assert c.extract_window("the 23rd of June") == (datetime(2026, 6, 23), datetime(2026, 6, 24))


def test_bare_ordinal_needs_month_context():
    assert c.extract_window("the 23rd") is None


def test_bare_ordinal_resolves_from_earlier_month_mention():
    """This is the whole point of replaying the transcript."""
    transcript = "what happened in june\nthe 23rd"
    assert c.extract_window(transcript) == (datetime(2026, 6, 23), datetime(2026, 6, 24))


def test_no_date_is_none():
    assert c.extract_window("why did revenue drop") is None


# ---- slot accumulation across turns ---------------------------------------

def test_first_turn_is_missing_the_window():
    slots = c.fill_slots(req("why did revenue drop?"))

    assert slots.metric == "revenue"
    assert slots.missing == ["window"]
    assert slots.ready is False


def test_second_turn_completes_the_slots():
    """The metric came from turn 1; the date from turn 2."""
    slots = c.fill_slots(req("why did revenue drop in june?", "the 23rd"))

    assert slots.metric == "revenue"
    assert slots.window_start == datetime(2026, 6, 23)
    assert slots.ready is True
    assert slots.missing == []


def test_single_turn_can_be_complete():
    slots = c.fill_slots(req("why did fill rate drop on june 23?"))

    assert (slots.metric, slots.ready) == ("fill_rate", True)


def test_later_mention_overrides_earlier():
    slots = c.fill_slots(req("revenue on june 23", "actually show me ctr on june 28"))

    assert slots.metric == "ctr"
    assert slots.window_start == datetime(2026, 6, 28)


def test_missing_both_slots():
    assert c.fill_slots(req("something looks off")).missing == ["metric", "window"]


# ---- intent routing --------------------------------------------------------

@pytest.mark.parametrize("text", ["hi", "hello", "thanks", "OK"])
def test_greeting_intent(text):
    r = req(text)
    assert c.classify(r, c.fill_slots(r)) == "greeting"


def test_scan_intent():
    r = req("what's wrong today?")
    assert c.classify(r, c.fill_slots(r)) == "scan"


def test_incomplete_slots_route_to_followup():
    r = req("why did revenue drop?")
    assert c.classify(r, c.fill_slots(r)) == "followup"


def test_complete_slots_route_to_investigate():
    r = req("why did revenue drop on june 23?")
    assert c.classify(r, c.fill_slots(r)) == "investigate"


# ---- OpenAI wire format ----------------------------------------------------

def test_completion_is_a_valid_openai_shape():
    """LibreChat reads choices[0].message.content and nothing else."""
    payload = c.completion("hello", context_id="ctx-1", slots=c.Slots())

    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"] == {"role": "assistant", "content": "hello"}
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["id"].startswith("chatcmpl-")
    assert payload["model"] == c.MODEL_NAME


def test_completion_carries_our_fields_alongside():
    """The dashboard's data rides in the same payload; OpenAI clients ignore it."""
    slots = c.Slots(metric="fill_rate", window_start=datetime(2026, 6, 23),
                    window_end=datetime(2026, 6, 26))

    payload = c.completion("diagnosis", context_id="ctx-9", slots=slots,
                           investigation={"investigation_id": "abc"})

    assert payload["template"] == {"metric": "fill_rate", "window": "2026-06-23/2026-06-26",
                                   "segment": None, "contextId": "ctx-9"}
    assert payload["isReadyForInvestigation"] is True
    assert payload["missingFields"] == []
    assert payload["investigation"]["investigation_id"] == "abc"
    assert payload["contextId"] == "ctx-9"


def test_last_user_message_ignores_assistant_turns():
    r = req("why did revenue drop?", "the 23rd")
    assert r.last_user_message() == "the 23rd"


def test_transcript_includes_only_user_turns():
    r = req("why did revenue drop?", "the 23rd")
    assert "Which time period?" not in r.transcript()
    assert "the 23rd" in r.transcript()


def test_ask_for_missing_names_the_gap():
    assert "time period" in c.ask_for_missing(c.Slots(metric="revenue")).lower()
    assert "metric" in c.ask_for_missing(c.Slots(window_start=datetime(2026, 6, 23))).lower()
