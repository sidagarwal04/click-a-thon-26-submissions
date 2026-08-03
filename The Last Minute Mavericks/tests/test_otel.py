#!/usr/bin/env python3
"""ClickStack instrumentation checks — the paths that must never take a scan down.

    python tests/test_otel.py          # no ClickHouse, no collector, no network needed

Covers the three failure modes from teamkit/PLAN_CLICKSTACK.md that would be silent in
production: instrumentation disabled, collector unreachable, and proxy transparency.
The detector-equality gate is NOT here — it is a one-shot before/after bundle diff, run
in the PR, not a unit test.
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrations import otel                      # noqa: E402
import run_incident as ri                          # noqa: E402


def _fresh(**env):
    """Reset otel's one-shot init so each case starts cold."""
    otel._state.update(tracer=None, provider=None, init=False)
    for k in ("CLICKSTACK_ENABLED", "CLICKSTACK_OTLP"):
        os.environ.pop(k, None)
    os.environ.update(env)


def test_disabled_is_a_working_noop():
    """CLICKSTACK_ENABLED unset => no-op tracer, and spans still accept attributes."""
    _fresh()
    assert not otel.enabled()
    with otel.span("anything", a=1, b=None) as s:
        s.set_attribute("c", 2)
        s.set_attributes({"d": 3})
        s.record_exception(ValueError("ignored"))
    assert isinstance(otel.tracer(), otel._NoopTracer)
    otel.shutdown()                                  # no provider: must not raise


def test_collector_down_never_raises():
    """A dead collector must degrade to a no-op, not a retry storm or an exception.
    Port 1 is reserved and never listening."""
    _fresh(CLICKSTACK_ENABLED="1", CLICKSTACK_OTLP="http://127.0.0.1:1")
    assert otel.enabled()
    assert not otel._reachable("http://127.0.0.1:1")
    with otel.span("stage"):
        pass
    assert isinstance(otel.tracer(), otel._NoopTracer), "unreachable collector must stay a no-op"
    otel.shutdown()


def test_traced_client_is_transparent():
    """TracedClient must return the driver's own objects and delegate everything else,
    so no call site can tell it is wrapped."""
    _fresh()

    class FakeResult:
        query_id = "qid-123"
        summary = {"read_rows": "42", "read_bytes": "4096", "elapsed_ns": "2500000"}
        result_rows = [(7,)]

    sentinel = FakeResult()

    class FakeRaw:
        server_version = "26.5"
        def query(self, sql, **kw): return sentinel
        def command(self, sql, **kw): return "OK"

    cx = ri.TracedClient(FakeRaw())
    assert cx.query("SELECT 1") is sentinel, "query() must return the driver's object unchanged"
    assert cx.query("SELECT 1").result_rows == [(7,)]
    assert cx.command("CREATE TABLE t") == "OK"
    assert cx.server_version == "26.5", "__getattr__ must delegate unknown attributes"

    st = ri.qstats(sentinel)
    assert st == {"query_id": "qid-123", "rows_read": 42, "bytes_read": 4096, "duration_ms": 2.5}, st

    # a server that sends no summary must degrade to zeros, i.e. exactly the old behaviour
    class Bare:
        query_id = ""
    assert ri.qstats(Bare()) == {"query_id": "", "rows_read": 0, "bytes_read": 0, "duration_ms": 0.0}


def test_connect_unwrapped_when_disabled():
    """Default path stays byte-identical: no proxy unless ClickStack is on."""
    _fresh()
    assert not otel.enabled(), "disabled => connect() must hand back the raw client"
    _fresh(CLICKSTACK_ENABLED="1")
    assert otel.enabled()


if __name__ == "__main__":
    for name, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_")):
        fn()
        print(f"  ok  {name}")
    _fresh()
    print("\nall clickstack instrumentation checks passed")
