"""JAL-88: reshaping a Langfuse trace into the dashboard's customer-facing timeline.

The Langfuse UI is comprehensive but developer-facing. These tests pin the translation:
phase spans become steps with a plain-language headline, their sql:* children become the
evidence underneath, and a missing/unreachable trace degrades to `available: False` rather
than raising into the API.
"""
from datetime import datetime

import pytest

from narrator import trace_read


class FakeObs:
    def __init__(self, name, output=None, input=None, latency=0.1, parent=None, obs_id=None, minute=0):
        self.id = obs_id or name
        self.name, self.output, self.input = name, output, input
        self.latency, self.parent_observation_id = latency, parent
        self.start_time = datetime(2026, 6, 23, 10, minute)
        self.type = "SPAN"


class FakeScore:
    def __init__(self, name, value):
        self.name, self.value = name, value


class FakeTrace:
    def __init__(self, observations, latency=2.876, scores=None):
        self.id, self.name = "trace-1", "investigation:fill_rate"
        self.latency, self.observations = latency, observations
        self.scores = scores or [FakeScore("anomaly_score", -128.58)]
        self.tags, self.output = ["fill_rate"], {}


def _trace() -> FakeTrace:
    return FakeTrace([
        FakeObs("investigation:fill_rate", minute=0, obs_id="root"),
        FakeObs("detect", minute=1, obs_id="d1", parent="root", latency=0.64,
                input={"metric": "fill_rate"},
                output={"detected": True, "observed": 0.7508, "expected": 0.7852,
                        "score": -128.58, "direction": "drop"}),
        FakeObs("sql:window-metric:fill_rate", minute=2, parent="d1", latency=0.12,
                input="SELECT sum(fills)/sum(requests) FROM hourly_summary",
                output={"row_count": 1}),
        FakeObs("depth-0:os_version", minute=3, obs_id="p0", parent="dr", latency=1.04,
                output={"decision": "descend", "winner": {"os_version": "Android 15"},
                        "contribution_pct": 0.9767, "lift": 10.2}),
        FakeObs("depth-1:stop", minute=4, parent="dr", latency=0.4,
                output={"decision": "stop", "reason": "no segment clears contribution>=0.5"}),
        FakeObs("ruled-out", minute=5, parent="root", latency=0.01,
                output={"cleared": {"ecpm_price": "ecpm moved +0.0% — within noise"}}),
    ])


@pytest.fixture
def view():
    return trace_read.shape(_trace())


def test_only_phases_become_steps_in_order(view):
    """The root and sql:* spans are not steps — the customer reads phases, not plumbing."""
    assert [s["phase"] for s in view["steps"]] == [
        "detect", "depth-0:os_version", "depth-1:stop", "ruled-out"
    ]


def test_sql_children_nest_under_their_phase(view):
    detect = view["steps"][0]

    assert len(detect["queries"]) == 1
    assert detect["queries"][0]["name"] == "sql:window-metric:fill_rate"
    assert detect["queries"][0]["sql"].startswith("SELECT sum(fills)")
    assert detect["queries"][0]["ms"] == 120


def test_durations_and_totals_are_milliseconds(view):
    assert view["total_ms"] == 2876
    assert view["steps"][0]["ms"] == 640


def test_scores_are_surfaced(view):
    assert view["scores"] == {"anomaly_score": -128.58}


def test_detect_headline_is_plain_language(view):
    headline = view["steps"][0]["headline"]

    assert "fill_rate" in headline and "0.751" in headline and "0.785" in headline
    assert "drop" in headline


def test_descend_headline_names_segment_and_evidence(view):
    headline = view["steps"][1]["headline"]

    # The dimension appears once (in "Split by"), the value once — not "os_version = os_version".
    assert headline.startswith("Split by os_version → Android 15")
    assert "97.7%" in headline and "10.2" in headline


def test_stop_headline_gives_the_reason(view):
    assert "no segment clears" in view["steps"][2]["headline"]


def test_ruled_out_headline_counts_cleared_hypotheses(view):
    assert "ecpm_price" in view["steps"][3]["headline"]


def test_unavailable_without_a_trace_id(monkeypatch):
    monkeypatch.setattr(trace_read, "langfuse", lambda: object())

    out = trace_read.trace_view(None)

    assert out["available"] is False
    assert out["reason"]


def test_unavailable_when_langfuse_is_off(monkeypatch):
    monkeypatch.setattr(trace_read, "langfuse", lambda: None)

    assert trace_read.trace_view("trace-1")["available"] is False


def test_fetch_failure_degrades_instead_of_raising(monkeypatch):
    class Boom:
        class api:
            class trace:
                @staticmethod
                def get(_id):
                    raise RuntimeError("langfuse unreachable")

    monkeypatch.setattr(trace_read, "langfuse", lambda: Boom())

    out = trace_read.trace_view("trace-1")

    assert out["available"] is False
    assert "unreachable" in out["reason"]
