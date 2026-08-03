"""
Telemetry for ClickStack, built on the official ClickStack Python SDK
(`hyperdx-opentelemetry`).

`configure_opentelemetry()` wires traces + logs to the OTLP endpoint (the local
`clickstack-otel-collector`, which forwards to ClickHouse Cloud). On top of that
we add a metrics pipeline and a set of custom instruments so insert/query
latency, rows/sec and error counts show up in HyperDX.

Design goals:
  * `init_telemetry()` is idempotent and safe to call anywhere. The `get_*`
    helpers call it for you, so "just import and use it" works with no setup.
  * If telemetry is disabled (TELEMETRY_ENABLED=false) or the SDK is missing,
    every instrument degrades to a no-op — the app still runs.
  * Endpoint / service name / headers come from the standard OTEL_* env vars.
"""

import atexit
import logging
import os
from contextlib import contextmanager
from functools import wraps

from .config import get_settings

log = logging.getLogger(__name__)


class _NoopInstrument:
    """Stand-in used before init / when telemetry is off. Accepts any call."""

    def add(self, *args, **kwargs):
        pass

    def record(self, *args, **kwargs):
        pass


_NOOP = _NoopInstrument()

# Public handles. Reassigned by init_telemetry(); safe to reference before init.
tracer = None
meter = None

insert_rows = _NOOP
insert_batches = _NOOP
insert_duration = _NOOP
query_rows = _NOOP
query_duration = _NOOP
consume_batch_size = _NOOP
errors = _NOOP

_state = {"initialized": False, "enabled": False}
_providers = {}


@contextmanager
def span(name, attributes=None):
    """Start a span if tracing is active, else a no-op. Yields the span or None."""
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as sp:
        if attributes:
            for key, value in attributes.items():
                sp.set_attribute(key, value)
        yield sp


def traced(name=None, attributes=None):
    """Decorator: wrap a function call in a span (named after it by default)."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with span(name or fn.__qualname__, attributes):
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def init_telemetry(service_name=None, force=False):
    """Configure ClickStack telemetry. Idempotent; no-op after first call."""
    if _state["initialized"] and not force:
        return

    cfg = get_settings().telemetry
    enabled = cfg.enabled
    if enabled:
        try:
            _setup_sdk(cfg, service_name)
            _state["enabled"] = True
            log.info(
                "Telemetry -> ClickStack collector at %s (service=%s)",
                cfg.endpoint,
                service_name or cfg.service_name,
            )
        except Exception as exc:  # never let observability break the app
            log.warning("Telemetry setup failed (%s); continuing without it.", exc)
            enabled = False
            _use_noop()
    else:
        _use_noop()

    _create_instruments()
    _state["initialized"] = True


def _setup_sdk(cfg, service_name):
    """Configure traces+logs via the ClickStack SDK, then add metrics ourselves."""
    global tracer, meter

    name = service_name or cfg.service_name

    # Feed our config into the standard OTel env vars the SDK reads.
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", cfg.endpoint)
    os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", cfg.protocol)
    # Force the service name so hyperdx (traces/logs, reads env) and our own
    # metrics Resource always agree on the same value.
    os.environ["OTEL_SERVICE_NAME"] = name
    if cfg.headers:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_HEADERS", cfg.headers)

    from hyperdx.opentelemetry import configure_opentelemetry

    configure_opentelemetry()  # traces + logs -> OTLP

    from opentelemetry import trace

    tracer = trace.get_tracer("ingester")
    meter = _setup_metrics(cfg, name)


def _setup_metrics(cfg, service_name):
    """Install a metrics pipeline (the ClickStack SDK only sets traces+logs)."""
    from opentelemetry import metrics

    try:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        if cfg.protocol.startswith("grpc"):
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
        else:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(), export_interval_millis=cfg.metric_interval_ms
        )
        resource = Resource.create({"service.name": service_name or cfg.service_name})
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        _providers["meter"] = provider
    except Exception as exc:
        # If a provider is already set (or SDK metrics unavailable), just use
        # whatever is registered — spans still carry the latency data.
        log.warning("Metrics pipeline not installed (%s); using span timings.", exc)

    return metrics.get_meter("ingester")


def _use_noop():
    global tracer, meter
    try:
        from opentelemetry import metrics, trace

        tracer = trace.get_tracer("ingester")
        meter = metrics.get_meter("ingester")
    except Exception:
        tracer = None
        meter = None


def _create_instruments():
    global insert_rows, insert_batches, insert_duration
    global query_rows, query_duration, consume_batch_size, errors

    if meter is None:
        insert_rows = insert_batches = insert_duration = _NOOP
        query_rows = query_duration = consume_batch_size = errors = _NOOP
        return

    insert_rows = meter.create_counter(
        "ingester.insert.rows", unit="{row}", description="Rows inserted into ClickHouse"
    )
    insert_batches = meter.create_counter(
        "ingester.insert.batches", unit="{batch}", description="Insert batches executed"
    )
    insert_duration = meter.create_histogram(
        "ingester.insert.duration", unit="ms", description="ClickHouse insert latency"
    )
    query_rows = meter.create_counter(
        "ingester.query.rows", unit="{row}", description="Rows returned by queries"
    )
    query_duration = meter.create_histogram(
        "ingester.query.duration", unit="ms", description="ClickHouse query latency"
    )
    consume_batch_size = meter.create_histogram(
        "ingester.consume.batch_size",
        unit="{event}",
        description="Events read per consume cycle",
    )
    errors = meter.create_counter(
        "ingester.errors", unit="{error}", description="Errors by stage/operation"
    )


def shutdown_telemetry():
    """Flush + shut down providers so short-lived scripts export before exit."""
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass

    meter_provider = _providers.get("meter")
    if meter_provider is not None:
        try:
            meter_provider.force_flush()
            meter_provider.shutdown()
        except Exception:
            pass
    _providers.clear()


atexit.register(shutdown_telemetry)
