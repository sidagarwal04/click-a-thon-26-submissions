"""The ClickHouse client is memoized so one pooled connection is reused across queries."""
from data import client as ch


def test_get_client_is_memoized(monkeypatch):
    created = []

    def fake_get_client(**kwargs):
        obj = object()
        created.append(obj)
        return obj

    monkeypatch.setattr(ch.clickhouse_connect, "get_client", fake_get_client)
    ch.get_client.cache_clear()
    try:
        first = ch.get_client()
        second = ch.get_client()
        assert first is second       # same client instance reused
        assert len(created) == 1     # underlying connection built only once
    finally:
        ch.get_client.cache_clear()


class _SpanRecorder:
    """Fake Langfuse: counts spans; get_current_trace_id switchable."""

    def __init__(self, active):
        self.active, self.spans = active, []

    def get_current_trace_id(self):
        return self.active

    def start_as_current_observation(self, *, name, as_type):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            class S:
                id = "span-1"

                def update(self, **kw):
                    pass

            self.spans.append(name)
            yield S()

        return cm()


def _stub_execute(monkeypatch):
    monkeypatch.setattr(
        ch, "_execute",
        lambda sql, params: {"rows": [], "columns": [], "resolved_sql": sql, "elapsed_ms": 0.0},
    )


def test_run_query_emits_no_span_outside_a_trace(monkeypatch):
    """Dev-console/benchmark queries must not create orphan traces."""
    lf = _SpanRecorder(active=None)
    monkeypatch.setattr(ch, "langfuse", lambda: lf)
    _stub_execute(monkeypatch)

    out = ch.run_query("SELECT 1")

    assert lf.spans == []
    assert "langfuse_span_id" not in out


def test_run_query_spans_inside_a_trace(monkeypatch):
    lf = _SpanRecorder(active="trace-1")
    monkeypatch.setattr(ch, "langfuse", lambda: lf)
    _stub_execute(monkeypatch)

    out = ch.run_query("SELECT 1", name="sql:baseline")

    assert lf.spans == ["sql:baseline"]
    assert out["langfuse_span_id"] == "span-1"
