"""An unconfigured deployment must not pay for observability.

The product's operating budget is small and deliberately so. Telemetry that
quietly opens a connection, buffers aggregates, or requires a vendor account
before the service will start is a recurring bill for something nobody asked
for. So the contract is: no endpoint configured means no exporter, no reader,
no background thread, and no network.

This matters more than it looks. `PeriodicExportingMetricReader` runs a timer
thread and accumulates every data point whether or not anything collects them,
so installing one "just in case" is not free — it is a memory cost forever and
a spend the moment somebody sets an endpoint they forgot about.
"""

from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.metrics import _internal as metrics_internal
from opentelemetry.sdk.metrics import MeterProvider

from zentra_adapter_telemetry import TelemetrySettings, configure_telemetry
from zentra_adapter_telemetry.metrics import configure_metrics


def test_no_endpoint_installs_no_meter_provider() -> None:
    before = metrics_internal._METER_PROVIDER  # noqa: SLF001

    configure_metrics(service_name="zentra-api", otlp_endpoint=None, otlp_headers=None)

    assert metrics_internal._METER_PROVIDER is before  # noqa: SLF001


def test_no_endpoint_installs_no_exporting_reader() -> None:
    """The expensive part is the reader, not the provider."""
    configure_metrics(service_name="zentra-api", otlp_endpoint="", otlp_headers=None)

    provider = metrics_internal._METER_PROVIDER  # noqa: SLF001
    assert not isinstance(provider, MeterProvider)


def test_configuring_the_app_without_an_endpoint_touches_no_provider() -> None:
    tracer_before = trace._TRACER_PROVIDER  # noqa: SLF001
    meter_before = metrics_internal._METER_PROVIDER  # noqa: SLF001

    configure_telemetry(FastAPI(), TelemetrySettings())

    assert trace._TRACER_PROVIDER is tracer_before  # noqa: SLF001
    assert metrics_internal._METER_PROVIDER is meter_before  # noqa: SLF001


def test_recorders_are_safe_to_call_with_no_provider_installed() -> None:
    """A no-op provider must not be a crash.

    The recorders run on every Investigation. If they raised when telemetry was
    unconfigured, the cheapest possible deployment would be the one that does
    not work.
    """
    from zentra_adapter_telemetry import (
        record_citation_resolution,
        record_evidence_deletion,
        record_publication_decision,
    )

    record_publication_decision(decision="published", failed_conditions=())
    record_citation_resolution(state="active", duration_ms=4)
    record_evidence_deletion(
        erasure_id="00000000-0000-0000-0000-000000000000",
        progress="completed",
        attempts=1,
        duration_ms=10,
    )
