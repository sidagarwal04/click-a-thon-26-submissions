#!/usr/bin/env python3
"""ClickStack (OpenTelemetry -> HyperDX) instrumentation for the RCA engine.

The 4th "ClickHouse three ways" leg: ClickStack stores its OTel data in ClickHouse
tables (otel_traces, otel_logs), so our latency telemetry is queryable with the same
SQL as our business data -- JOIN-able in one statement.

Everything here is OFF unless CLICKSTACK_ENABLED=1, and every failure path degrades to
a no-op tracer. A scan must complete identically whether the collector is up, down, or
the OTel packages are not installed at all.

  CLICKSTACK_ENABLED=1            enable (anything else = fully off)
  CLICKSTACK_OTLP=http://host:4318  OTLP HTTP base (default http://localhost:4318)
  CLICKSTACK_API_KEY=<key>       ingestion key for the AUTH image (HyperDX all-in-one, which
                                 401s unauthenticated OTLP). Omit for the local-mode image.

Bring-up:  docker compose -f integrations/clickstack/docker-compose.yml up -d
GUARDRAIL: ClickStack writes to its OWN bundled ClickHouse, never CLICKHOUSE_HOST.
"""
import atexit, os
from contextlib import contextmanager

SERVICE_NAME = "rca-engine"
TRACER_NAME = "rca.clickhouse"  # contractual: Langfuse blocks this scope (CLAUDE.md:75)

_state = {"tracer": None, "provider": None, "init": False}


class _NoopSpan:
    def set_attribute(self, *a, **k): pass
    def set_attributes(self, *a, **k): pass
    def record_exception(self, *a, **k): pass


class _NoopTracer:
    """Stands in when OTel is disabled, missing, or broken. Same surface, zero cost."""
    @contextmanager
    def start_as_current_span(self, *a, **k):
        yield _NoopSpan()


def enabled() -> bool:
    return os.environ.get("CLICKSTACK_ENABLED", "").strip() == "1"


def _reachable(base: str, timeout: float = 0.4) -> bool:
    """Is the OTLP collector actually listening? One TCP connect, 400ms budget."""
    import socket
    from urllib.parse import urlparse
    u = urlparse(base)
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 4318), timeout):
            return True
    except OSError:
        return False


def tracer():
    """The tracer for this process. Never raises, never returns None."""
    if _state["init"]:
        return _state["tracer"]
    _state["init"] = True
    _state["tracer"] = _NoopTracer()
    if not enabled():
        return _state["tracer"]
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        base = os.environ.get("CLICKSTACK_OTLP", "http://localhost:4318").rstrip("/")
        if not _reachable(base):
            # Don't start an exporter we can't reach. Without this, a stopped container costs a
            # retry storm on stderr mid-demo and ~17s of blocked shutdown at exit. One honest
            # line beats three red tracebacks over telemetry nobody asked about.
            # ponytail: checked once at init — a collector that dies mid-run still degrades via
            # BatchSpanProcessor's own drop path (verified); restart the process to re-attach.
            print(f"  (clickstack: no collector at {base} — telemetry off, scan unaffected)")
            return _state["tracer"]
        provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
        # Auth image (HyperDX all-in-one) 401s OTLP without an ingestion key; local-mode needs
        # none. Send the header only when a key is set, so both images work off one code path.
        key = os.environ.get("CLICKSTACK_API_KEY", "").strip()
        headers = {"authorization": key} if key else None
        # BatchSpanProcessor retries then DROPS on a dead collector -- the export thread
        # never propagates back into the scan. That is the whole failure story.
        # timeout bounds the mid-run-death case: retries give up fast instead of stalling exit.
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers, timeout=5)))
        # Deliberately NOT trace.set_tracer_provider(): Langfuse v4 is OTel-based too, and
        # owning the GLOBAL provider makes its reasoning spans ("RCA scan · rca", one per
        # incident) export through our collector — verified, they showed up in otel_traces.
        # A private provider isolates both directions: ClickStack gets latency, Langfuse
        # gets reasoning, neither pollutes the other.
        _state["provider"] = provider
        _state["tracer"] = provider.get_tracer(TRACER_NAME)
        # THE classic OTel footgun: a short-lived CLI exits before the batch timer fires and
        # every span is silently lost. atexit covers every entrypoint (CLI, API, SystemExit)
        # in one line instead of a try/finally per __main__.
        atexit.register(shutdown)
    except Exception as e:  # missing deps, bad endpoint, anything: stay a no-op
        print(f"  (clickstack disabled: {e})")
    return _state["tracer"]


def shutdown():
    """Flush pending spans. THE classic OTel footgun: a short-lived CLI exits before
    BatchSpanProcessor's timer fires and every span is silently lost. Call in a finally."""
    p = _state.get("provider")
    if p is None:
        return
    try:
        p.shutdown()
    except Exception:
        pass


@contextmanager
def span(name, **attrs):
    """Stage span. Safe to use unconditionally -- no-op when disabled."""
    with tracer().start_as_current_span(name) as s:
        for k, v in attrs.items():
            if v is not None:
                s.set_attribute(k, v)
        yield s


def demo() -> None:
    """Self-check: the disabled path must be a working no-op with no OTel installed."""
    _state.update(tracer=None, provider=None, init=False)
    os.environ.pop("CLICKSTACK_ENABLED", None)
    assert not enabled()
    with span("t", a=1) as s:
        s.set_attribute("b", 2)          # must not raise
    assert isinstance(tracer(), _NoopTracer)
    shutdown()                            # must not raise with no provider
    print("otel.py disabled-path OK")


if __name__ == "__main__":
    demo()
