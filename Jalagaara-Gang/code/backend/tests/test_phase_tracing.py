"""phase(): nested judge-readable spans. No Langfuse / no active trace => clean no-op."""
from contextlib import contextmanager

import pytest

from narrator import tracing


class FakeSpan:
    def __init__(self, tree, name):
        self.tree, self.name, self.updates = tree, name, []

    def update(self, **kw):
        self.updates.append(kw)


class FakeLangfuse:
    """Minimal v4 surface: records a flat list of (event, payload) in order."""

    def __init__(self, active_trace="trace-1"):
        self.events = []
        self._active = active_trace

    def get_current_trace_id(self):
        return self._active

    @contextmanager
    def start_as_current_observation(self, *, name, as_type):
        span = FakeSpan(self.events, name)
        self.events.append(("open", name, as_type))
        yield span
        self.events.append(("close", name, span.updates))

    def flush(self):
        self.events.append(("flush", None, None))


@pytest.fixture
def fake_lf(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    return lf


def test_phase_opens_named_span_and_records_verdict(fake_lf):
    with tracing.phase("decompose", input={"metric": "revenue"}) as p:
        p.verdict(primary_factor="fill_rate", decision="descend")

    opens = [e for e in fake_lf.events if e[0] == "open"]
    assert opens == [("open", "decompose", "span")]
    closes = next(e for e in fake_lf.events if e[0] == "close")
    updates = closes[2]
    # input recorded at open, verdict recorded as output
    assert {"input": {"metric": "revenue"}} in updates
    assert {"output": {"primary_factor": "fill_rate", "decision": "descend"}} in updates


def test_phase_flushes_on_exit_when_live_flush(fake_lf, monkeypatch):
    monkeypatch.setitem(tracing._TRACING, "live_flush", True)
    with tracing.phase("detect"):
        pass
    assert fake_lf.events[-1] == ("flush", None, None)


def test_phase_no_flush_when_disabled(fake_lf, monkeypatch):
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    with tracing.phase("detect"):
        pass
    assert ("flush", None, None) not in fake_lf.events


def test_phase_noop_without_langfuse(monkeypatch):
    monkeypatch.setattr(tracing, "langfuse", lambda: None)
    with tracing.phase("detect") as p:
        p.verdict(anything=1)  # must not raise
    assert p.enabled is False


def test_phase_noop_without_active_trace(monkeypatch):
    lf = FakeLangfuse(active_trace=None)
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    with tracing.phase("detect") as p:
        p.verdict(anything=1)
    assert p.enabled is False
    assert lf.events == []  # no orphan span created


def test_stamp_trace_verdict_sets_output_and_score(fake_lf):
    calls = {}
    fake_lf.set_current_trace_io = lambda **kw: calls.setdefault("io", kw)
    fake_lf.score_current_trace = lambda **kw: calls.setdefault("score", kw)

    class B:  # duck-typed bundle
        class anomaly:
            detected, score, pct_delta = True, -4.2, -0.1

        class factor_decomposition:
            primary_factor = "fill_rate"

        localized_segment = {"country": "IN"}
        metric = "revenue"

    tracing.stamp_trace_verdict(B)

    assert calls["io"]["output"]["primary_factor"] == "fill_rate"
    assert calls["io"]["output"]["localized_segment"] == {"country": "IN"}
    assert calls["score"] == {"name": "anomaly_score", "value": -4.2, "data_type": "NUMERIC"}


def test_score_trace_noop_without_langfuse(monkeypatch):
    monkeypatch.setattr(tracing, "langfuse", lambda: None)
    tracing.score_trace("guardrail_passed", 1, "BOOLEAN")  # must not raise
