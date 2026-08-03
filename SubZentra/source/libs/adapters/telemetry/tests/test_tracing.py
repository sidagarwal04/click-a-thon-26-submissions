from uuid import UUID

from fastapi import FastAPI

from zentra_adapter_telemetry import (
    TelemetrySettings,
    configure_telemetry,
    correlate_tenant,
)


def test_configures_local_instrumentation_without_exporter() -> None:
    app = FastAPI()

    configure_telemetry(app, TelemetrySettings())

    assert app is not None


def test_correlates_internal_tenant_on_the_active_span(monkeypatch) -> None:
    attributes = {}

    class Span:
        def set_attribute(self, name: str, value: str) -> None:
            attributes[name] = value

    monkeypatch.setattr(
        "zentra_adapter_telemetry.tracing.trace.get_current_span",
        lambda: Span(),
    )
    tenant_id = UUID("91000000-0000-0000-0000-000000000001")

    correlate_tenant(tenant_id)

    assert attributes == {"zentra.tenant_id": str(tenant_id)}
