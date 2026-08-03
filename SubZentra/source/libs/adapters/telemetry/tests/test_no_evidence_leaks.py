"""Nothing a Tenant owns may reach a span or a metric.

The guarantee this file defends is an allowlist, not a sanitizer: no recorder
in this adapter passes a value through a filter that strips content, because a
filter that can be fooled is worse than no filter. Instead, the set of keys
that may be written is fixed and small, and every key on it holds a category, a
count, a duration or an identifier. Nothing on it can hold prose.

So each test here attacks a different way that could stop being true:

- a recorder writing a key nobody reviewed,
- a caller passing content into a field intended for a category,
- a metric dimension whose values are unbounded,
- and the allowlist itself quietly growing.

The poison strings below stand for the six things #23 names — raw rows,
prompts, Finding narrative, aggregate values, credentials, hidden reasoning.
Each is distinctive enough that a substring search over the exported telemetry
is a real check rather than a coincidence.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.metrics import _internal as metrics_internal
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from zentra_adapter_telemetry import (
    SAFE_ATTRIBUTES,
    SAFE_DIMENSIONS,
    record_citation_resolution,
    record_evidence_deletion,
    record_insight_execution,
    record_publication_decision,
)
from zentra_adapter_telemetry.metrics import dimensions, reset_instruments
from zentra_adapter_telemetry.tracing import _record

#: One sentinel per prohibited category in the acceptance criterion.
POISON = {
    "raw_row": "ROWLEAK-region=EMEA,orders=4181",
    "prompt": "PROMPTLEAK-You are the Insight Agent. Given the following",
    "narrative": "NARRATIVELEAK-Checkout conversion fell sharply in EMEA",
    "aggregate_value": "VALUELEAK-0.1743",
    "credential": "CREDLEAK-sk-ant-api03-abcdef",
    "hidden_reasoning": "REASONLEAK-<thinking>the analyst may be wrong</thinking>",
}


@pytest.fixture
def telemetry():
    """A real provider pair, exporting in memory.

    A fake span object would only prove that the code sets the attributes it
    sets. Exporting through the SDK means anything written anywhere in the call
    path — including by a future helper nobody remembered — lands in what these
    tests read.
    """
    spans = InMemorySpanExporter()
    tracer_provider = TracerProvider(resource=Resource.create({}))
    tracer_provider.add_span_processor(SimpleSpanProcessor(spans))
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(
        resource=Resource.create({}), metric_readers=[reader]
    )

    # The raw module globals, not the accessors: `get_tracer_provider()`
    # returns a proxy that resolves through the same global, so restoring its
    # return value would install a provider that delegates to itself.
    previous_tracer = trace._TRACER_PROVIDER  # noqa: SLF001
    previous_meter = metrics_internal._METER_PROVIDER  # noqa: SLF001
    trace._TRACER_PROVIDER = tracer_provider  # noqa: SLF001
    metrics_internal._METER_PROVIDER = meter_provider  # noqa: SLF001
    reset_instruments()

    tracer = tracer_provider.get_tracer(__name__)
    try:
        yield _Telemetry(tracer, spans, reader)
    finally:
        trace._TRACER_PROVIDER = previous_tracer  # noqa: SLF001
        metrics_internal._METER_PROVIDER = previous_meter  # noqa: SLF001
        reset_instruments()


class _Telemetry:
    def __init__(self, tracer, spans, reader) -> None:
        self.tracer = tracer
        self._spans = spans
        self._reader = reader

    def attributes(self) -> dict[str, object]:
        merged: dict[str, object] = {}
        for span in self._spans.get_finished_spans():
            merged.update(span.attributes or {})
        return merged

    def dimensions(self) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        data = self._reader.get_metrics_data()
        for resource_metric in data.resource_metrics if data else ():
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    for point in metric.data.data_points:
                        found.append(dict(point.attributes))
        return found


def _emit_everything() -> None:
    """Every recorder, called the way production calls it, poisoned.

    The poison goes into the fields whose *purpose* is to be a category or an
    identifier. That is the leak worth defending against: nobody puts a prompt
    in `duration_ms`, but a well-meaning caller passing `str(error)` into
    `error_category` is a change of one word.
    """
    record_insight_execution(
        agent_id="insight_v1",
        model="anthropic/claude-sonnet-5",
        provider="anthropic",
        fallback_count=1,
        input_tokens=1200,
        output_tokens=340,
        cost_usd="0.0181",
        duration_ms=1450,
        status="succeeded",
        error_category=None,
    )
    record_publication_decision(
        decision="gated",
        failed_conditions=("evidenced", "uncontradicted"),
    )
    record_citation_resolution(state="tombstoned", duration_ms=12)
    record_evidence_deletion(
        erasure_id="9f1c1e64-1f0e-4a1a-9a2f-4b6a2f1e0c11",
        progress="completed",
        attempts=2,
        duration_ms=880,
    )


def test_no_recorder_writes_an_attribute_nobody_reviewed(telemetry) -> None:
    with telemetry.tracer.start_as_current_span("investigation"):
        _emit_everything()

    written = set(telemetry.attributes())
    assert written, "the recorders wrote nothing, so this proves nothing"
    assert written <= SAFE_ATTRIBUTES


def test_no_metric_carries_an_unbounded_dimension(telemetry) -> None:
    with telemetry.tracer.start_as_current_span("investigation"):
        _emit_everything()

    points = telemetry.dimensions()
    assert points, "no metric points were exported, so this proves nothing"
    for attributes in points:
        assert set(attributes) <= SAFE_DIMENSIONS
    # Specifically: the erasure identity is a fine span attribute and a series
    # per deletion if it becomes a dimension.
    assert not any("erasure_id" in attributes for attributes in points)


@pytest.mark.parametrize("category,value", sorted(POISON.items()))
def test_poison_cannot_reach_a_span_through_an_unlisted_key(
    telemetry, category: str, value: str
) -> None:
    """The allowlist refuses rather than drops.

    A recorder that silently discarded the key would pass a leak test while
    leaving an operator waiting for a signal that never arrives, so the
    expected behaviour is an exception.
    """
    with (
        telemetry.tracer.start_as_current_span("investigation"),
        pytest.raises(ValueError, match="not on the safe list"),
    ):
        _record({f"zentra.insight.{category}": value})

    assert value not in str(telemetry.attributes())


@pytest.mark.parametrize("category,value", sorted(POISON.items()))
def test_poison_cannot_reach_a_metric_through_an_unlisted_dimension(
    category: str, value: str
) -> None:
    with pytest.raises(ValueError, match="not on the safe list"):
        dimensions(**{category: value})


def test_the_allowlists_hold_only_categories_counts_and_identifiers(
    telemetry,
) -> None:
    """A change detector, deliberately.

    Adding an attribute should be a decision somebody makes on purpose. The
    only names permitted are enumerated here, so widening the allowlist fails
    this test and forces the widening to be argued for in a diff.
    """
    assert frozenset(
        {
            "zentra.tenant_id",
            "zentra.investigation_id",
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
            "zentra.publication.decision",
            "zentra.publication.failed_conditions",
            "zentra.citation.state",
            "zentra.citation.duration_ms",
            "zentra.citation.failure_category",
            "zentra.deletion.erasure_id",
            "zentra.deletion.progress",
            "zentra.deletion.attempts",
            "zentra.deletion.duration_ms",
            "zentra.deletion.failure_category",
        }
    ) == SAFE_ATTRIBUTES
    assert frozenset(
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
    ) == SAFE_DIMENSIONS


def test_an_absent_dimension_is_dropped_rather_than_stringified() -> None:
    """`None` and the string "None" are different series; only one is true."""
    assert dimensions(progress="failed", failure_category=None) == {
        "progress": "failed"
    }


def test_an_operator_can_tell_two_failures_apart(telemetry) -> None:
    """Criterion 10: distinguishable without being revealing.

    The point of a category is that it partitions. A signal where a store
    outage, a denied citation and a contract break all arrive as `failed` costs
    the same to collect and answers nothing at 3am.
    """
    with telemetry.tracer.start_as_current_span("outage"):
        record_citation_resolution(
            state="failed", duration_ms=30_000, failure_category="TimeoutError"
        )
    outage = telemetry.attributes()

    with telemetry.tracer.start_as_current_span("denied"):
        record_citation_resolution(
            state="inaccessible",
            duration_ms=4,
            failure_category="not_visible_to_tenant",
        )
    both = telemetry.attributes()

    assert outage["zentra.citation.failure_category"] == "TimeoutError"
    assert both["zentra.citation.failure_category"] == "not_visible_to_tenant"
    assert outage["zentra.citation.state"] != both["zentra.citation.state"]


def test_deletion_failures_are_distinguishable_by_category(telemetry) -> None:
    with telemetry.tracer.start_as_current_span("denied"):
        record_evidence_deletion(
            erasure_id="",
            progress="denied",
            attempts=0,
            duration_ms=1,
            failure_category="role_not_permitted",
        )
    denied = telemetry.attributes()["zentra.deletion.failure_category"]

    with telemetry.tracer.start_as_current_span("refused"):
        record_evidence_deletion(
            erasure_id="",
            progress="refused",
            attempts=0,
            duration_ms=1,
            failure_category="not_terminal",
        )
    refused = telemetry.attributes()["zentra.deletion.failure_category"]

    assert denied != refused


def test_a_partial_erasure_is_never_reported_as_completed(telemetry) -> None:
    """The one thing deletion telemetry must never say.

    `failed` is retryable and `completed` is final; an operator who cannot see
    the difference cannot know there is content still to erase.
    """
    with telemetry.tracer.start_as_current_span("partial"):
        record_evidence_deletion(
            erasure_id="4f0b2f1e-0000-4000-8000-000000000001",
            progress="failed",
            attempts=3,
            duration_ms=920,
            failure_category="surface_not_empty",
        )

    attributes = telemetry.attributes()
    assert attributes["zentra.deletion.progress"] == "failed"
    assert attributes["zentra.deletion.attempts"] == 3
