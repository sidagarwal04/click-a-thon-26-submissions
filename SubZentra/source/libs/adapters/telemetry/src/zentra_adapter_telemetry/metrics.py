"""Aggregates, for the questions a single trace cannot answer.

Spans say what happened in one Investigation. "What does an Insight execution
cost us, and how long does it take?" is a question about all of them, and
answering it from sampled traces gives an answer shaped by the sampler rather
than by the system. So cost and latency are histograms as well as span
attributes, emitted from the same recorder call so the two signals cannot
drift.

The allowlist discipline from `tracing.py` applies here and then tightens. A
span attribute is written once and read by someone already looking at that
Investigation; a metric attribute becomes a time series per distinct value, for
ever. `zentra.deletion.erasure_id` is a perfectly safe span attribute and an
unbounded cardinality explosion as a metric dimension, so `SAFE_DIMENSIONS` is
a strict subset of `SAFE_ATTRIBUTES` rather than a copy of it.
"""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

#: Every dimension a Phase 2 metric may carry. Bounded sets only: a status, a
#: provider, a policy condition. Nothing that varies per Investigation, per
#: Tenant, or per erasure — those are span attributes, where they cost one
#: write instead of one time series.
SAFE_DIMENSIONS: frozenset[str] = frozenset(
    {
        "status",
        "provider",
        "model",
        "decision",
        "state",
        "condition",
        "progress",
        "failure_category",
        "error_category",
    }
)

_METER_NAME = "zentra.phase2"


def dimensions(**values: str | None) -> dict[str, str]:
    """Drop the absent, refuse the unlisted.

    Public because the recorders live in `tracing.py`; a private name imported
    across modules is a private name in title only.

    Unlike `_record` in `tracing.py`, a `None` here is dropped rather than
    written: an absent dimension and a dimension whose value is the string
    "None" are different series, and only one of them is true.
    """
    unknown = set(values) - SAFE_DIMENSIONS
    if unknown:
        raise ValueError(
            f"Metric dimension not on the safe list: {', '.join(sorted(unknown))}"
        )
    return {key: value for key, value in values.items() if value is not None}


class _Instruments:
    """Created once, on first use.

    Instrument creation binds to whichever MeterProvider is installed at the
    time. Building these at import would bind every process to the no-op
    provider that exists before `configure_metrics` runs.
    """

    def __init__(self) -> None:
        meter = metrics.get_meter(_METER_NAME)
        self.insight_duration = meter.create_histogram(
            "zentra.insight.duration",
            unit="ms",
            description="Wall time of one Insight Agent execution",
        )
        self.insight_cost = meter.create_histogram(
            "zentra.insight.cost",
            unit="USD",
            description="Provider cost of one Insight Agent execution",
        )
        self.insight_tokens = meter.create_histogram(
            "zentra.insight.tokens",
            unit="{token}",
            description="Tokens consumed by one Insight Agent execution",
        )
        self.insight_fallbacks = meter.create_counter(
            "zentra.insight.fallbacks",
            unit="{rung}",
            description="Fallback rungs descended before an Insight execution "
            "succeeded",
        )
        self.publication_decisions = meter.create_counter(
            "zentra.publication.decisions",
            unit="{decision}",
            description="Publication policy decisions, by outcome",
        )
        self.publication_failures = meter.create_counter(
            "zentra.publication.condition_failures",
            unit="{condition}",
            description="Publication conditions that failed, by condition",
        )
        self.citation_duration = meter.create_histogram(
            "zentra.citation.duration",
            unit="ms",
            description="Wall time of one Evidence Citation resolution",
        )
        self.deletion_duration = meter.create_histogram(
            "zentra.deletion.duration",
            unit="ms",
            description="Wall time of one evidence erasure",
        )
        self.deletion_operations = meter.create_counter(
            "zentra.deletion.operations",
            unit="{operation}",
            description="Evidence erasures, by progress state",
        )


_instruments: _Instruments | None = None


def instruments() -> _Instruments:
    global _instruments
    if _instruments is None:
        _instruments = _Instruments()
    return _instruments


def reset_instruments() -> None:
    """Rebind on the next use.

    Exists for tests, which install a fresh reader per case and would otherwise
    measure through instruments bound to a provider from an earlier one.
    """
    global _instruments
    _instruments = None


def configure_metrics(
    *,
    service_name: str,
    otlp_endpoint: str | None,
    otlp_headers: str | None,
) -> None:
    """Install a MeterProvider, or leave the no-op one alone.

    No endpoint means no reader: an unconfigured deployment should cost
    nothing, not accumulate aggregates nobody collects.
    """
    if not otlp_endpoint:
        return
    exporter = OTLPMetricExporter(
        endpoint=f"{otlp_endpoint.rstrip('/')}/v1/metrics",
        headers=_parse_headers(otlp_headers),
    )
    provider = MeterProvider(
        resource=Resource.create({"service.name": service_name}),
        metric_readers=[PeriodicExportingMetricReader(exporter)],
    )
    metrics.set_meter_provider(provider)
    reset_instruments()


def _parse_headers(raw: str | None) -> dict[str, str] | None:
    if not raw:
        return None
    pairs = (item.split("=", maxsplit=1) for item in raw.split(",") if "=" in item)
    return {key.strip(): value.strip() for key, value in pairs}
