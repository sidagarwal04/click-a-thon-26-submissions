from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .metrics import configure_metrics, dimensions, instruments


@dataclass(frozen=True, slots=True)
class TelemetrySettings:
    service_name: str = "zentra-api"
    otlp_endpoint: str | None = None
    otlp_headers: str | None = None


def correlate_tenant(tenant_id: UUID) -> None:
    trace.get_current_span().set_attribute("zentra.tenant_id", str(tenant_id))


#: Every attribute this module is allowed to set. An allowlist rather than a
#: convention, because a span attribute is one of the easiest places for
#: evidence to leak and "we remembered not to" is not a guarantee. The
#: regression test walks this list; adding a key here is a deliberate act.
SAFE_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "zentra.tenant_id",
        "zentra.investigation_id",
        # Insight execution
        "zentra.insight.agent_id",
        "zentra.insight.model",
        "zentra.insight.provider",
        "zentra.insight.fallback_count",
        "zentra.insight.input_tokens",
        "zentra.insight.output_tokens",
        "zentra.insight.cost_usd",
        "zentra.insight.duration_ms",
        "zentra.insight.status",
        "zentra.insight.error_category",
        # Publication policy
        "zentra.publication.decision",
        "zentra.publication.failed_conditions",
        # Citation resolution
        "zentra.citation.state",
        "zentra.citation.duration_ms",
        "zentra.citation.failure_category",
        # Evidence deletion
        "zentra.deletion.erasure_id",
        "zentra.deletion.progress",
        "zentra.deletion.attempts",
        "zentra.deletion.duration_ms",
        "zentra.deletion.failure_category",
    }
)


def _record(attributes: dict[str, object]) -> None:
    """Set span attributes, refusing anything not on the allowlist.

    Raising rather than dropping: a telemetry call that silently discarded a
    key would leave an operator waiting for a signal that never arrives, and a
    developer believing they had added one.
    """
    unknown = set(attributes) - SAFE_ATTRIBUTES
    if unknown:
        raise ValueError(
            f"Telemetry attribute not on the safe list: {', '.join(sorted(unknown))}"
        )
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def record_insight_execution(
    *,
    agent_id: str,
    model: str | None,
    provider: str | None,
    fallback_count: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: str,
    duration_ms: int,
    status: str,
    error_category: str | None = None,
) -> None:
    """What the Insight step cost and how it went.

    `fallback_count` rather than the rungs themselves: the number tells an
    operator the chain degraded, and the rung strings are already in the audit
    ledger where they belong. `error_category` is a category — an error message
    is the one field most likely to quote the evidence back.
    """
    _record(
        {
            "zentra.insight.agent_id": agent_id,
            "zentra.insight.model": model,
            "zentra.insight.provider": provider,
            "zentra.insight.fallback_count": fallback_count,
            "zentra.insight.input_tokens": input_tokens,
            "zentra.insight.output_tokens": output_tokens,
            "zentra.insight.cost_usd": cost_usd,
            "zentra.insight.duration_ms": duration_ms,
            "zentra.insight.status": status,
            "zentra.insight.error_category": error_category,
        }
    )
    dims = dimensions(status=status, provider=provider, model=model)
    meters = instruments()
    meters.insight_duration.record(duration_ms, dims)
    meters.insight_cost.record(float(cost_usd), dims)
    meters.insight_tokens.record(input_tokens + output_tokens, dims)
    if fallback_count:
        meters.insight_fallbacks.add(fallback_count, dims)


def record_publication_decision(
    *,
    decision: str,
    failed_conditions: tuple[str, ...],
) -> None:
    """Which conditions failed, in the policy's own vocabulary.

    The condition names are a closed set the product already publishes; none
    of them carries a figure, a claim or a Tenant's data.
    """
    _record(
        {
            "zentra.publication.decision": decision,
            "zentra.publication.failed_conditions": ",".join(failed_conditions),
        }
    )
    meters = instruments()
    meters.publication_decisions.add(1, dimensions(decision=decision))
    for condition in failed_conditions:
        # One series per condition rather than one per combination: an operator
        # asking "what is gating publication?" wants the conditions ranked, and
        # sixteen combination series cannot be ranked.
        meters.publication_failures.add(1, dimensions(condition=condition))


def record_citation_resolution(
    *,
    state: str,
    duration_ms: int,
    failure_category: str | None = None,
) -> None:
    """How a citation resolution went, how long it took, and why it did not.

    An operator needs to tell "slow" from "missing" from "denied" from "the
    store is down". The state answers the first three; without a category the
    fourth is indistinguishable from any other fault. None of it requires the
    evidence itself.
    """
    _record(
        {
            "zentra.citation.state": state,
            "zentra.citation.duration_ms": duration_ms,
            "zentra.citation.failure_category": failure_category,
        }
    )
    instruments().citation_duration.record(
        duration_ms,
        dimensions(state=state, failure_category=failure_category),
    )


def record_evidence_deletion(
    *,
    erasure_id: str,
    progress: str,
    attempts: int,
    duration_ms: int,
    failure_category: str | None = None,
) -> None:
    """How an erasure went, without any of what it erased.

    The erasure's own identity, not the Investigation's content. A deletion's
    telemetry is the last place the deleted value could hide.
    """
    _record(
        {
            "zentra.deletion.erasure_id": erasure_id,
            "zentra.deletion.progress": progress,
            "zentra.deletion.attempts": attempts,
            "zentra.deletion.duration_ms": duration_ms,
            "zentra.deletion.failure_category": failure_category,
        }
    )
    # No erasure_id: safe to write once on a span, an unbounded series here.
    dims = dimensions(progress=progress, failure_category=failure_category)
    meters = instruments()
    meters.deletion_duration.record(duration_ms, dims)
    meters.deletion_operations.add(1, dims)


def correlate_investigation(investigation_id: UUID) -> None:
    """Internal identifier only, so a trace can be followed to its work.

    Never the question, which is a Tenant's own words.
    """
    trace.get_current_span().set_attribute(
        "zentra.investigation_id", str(investigation_id)
    )


def current_trace_ids() -> tuple[UUID, UUID]:
    context = trace.get_current_span().get_span_context()
    trace_id = UUID(int=context.trace_id) if context.trace_id else uuid4()
    span_id = UUID(int=context.span_id) if context.span_id else uuid4()
    return trace_id, span_id


def configure_telemetry(app: FastAPI, settings: TelemetrySettings) -> None:
    if settings.otlp_endpoint:
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.service_name})
        )
        exporter = OTLPSpanExporter(
            endpoint=settings.otlp_endpoint,
            headers=settings.otlp_headers,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    configure_metrics(
        service_name=settings.service_name,
        otlp_endpoint=settings.otlp_endpoint,
        otlp_headers=settings.otlp_headers,
    )
    FastAPIInstrumentor.instrument_app(app)
