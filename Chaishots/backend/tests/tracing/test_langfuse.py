from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import app.tracing.langfuse as tracing_module
from app.tracing import LangfuseTracer, NoopTracer, create_tracer


class FakeObservation:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> object:
        self.updates.append(kwargs)
        return self


class FakeLangfuseClient:
    def __init__(self) -> None:
        self.starts: list[dict[str, object]] = []
        self.observations: list[FakeObservation] = []
        self.active: list[FakeObservation] = []
        self.parents: list[FakeObservation | None] = []
        self.flush_count = 0

    @contextmanager
    def start_as_current_observation(
        self, **kwargs: object
    ) -> Iterator[FakeObservation]:
        observation = FakeObservation(trace_id="trace-123")
        self.starts.append(kwargs)
        self.observations.append(observation)
        self.parents.append(self.active[-1] if self.active else None)
        self.active.append(observation)
        try:
            yield observation
        finally:
            popped = self.active.pop()
            assert popped is observation

    def flush(self) -> None:
        self.flush_count += 1


def test_noop_tracer_is_safe_for_nested_spans() -> None:
    tracer = NoopTracer()

    with tracer.span("outer", input={"count": 2}) as outer:
        with tracer.span("inner", as_type="tool") as inner:
            inner.update(
                output={"rows": 2},
                metadata={"table": "feature_events"},
                level="DEFAULT",
                status="complete",
            )

    assert outer.trace_id is None
    assert inner.trace_id is None
    tracer.flush()


def test_langfuse_tracer_forwards_only_explicit_payloads() -> None:
    client = FakeLangfuseClient()
    tracer = LangfuseTracer(client)

    with tracer.span("profile_events", as_type="tool") as span:
        span.update(
            output={"event_count": 12},
            metadata={"field_count": 4},
            level="WARNING",
            status="sparse optional field",
        )

    assert client.starts == [{"name": "profile_events", "as_type": "tool"}]
    assert client.observations[0].updates == [
        {
            "output": {"event_count": 12},
            "metadata": {"field_count": 4},
            "level": "WARNING",
            "status_message": "sparse optional field",
        }
    ]
    assert span.trace_id == "trace-123"


def test_langfuse_tracer_propagates_nested_current_observation() -> None:
    client = FakeLangfuseClient()
    tracer = LangfuseTracer(client)

    with tracer.span("process_feature", input={"feature": "06_hidden"}) as outer:
        with tracer.span("analytics_agent", as_type="agent") as inner:
            assert outer.trace_id == inner.trace_id

    assert client.starts == [
        {
            "name": "process_feature",
            "as_type": "span",
            "input": {"feature": "06_hidden"},
        },
        {"name": "analytics_agent", "as_type": "agent"},
    ]
    assert client.parents == [None, client.observations[0]]
    assert client.active == []


def test_flush_delegates_to_langfuse_client() -> None:
    client = FakeLangfuseClient()
    tracer = LangfuseTracer(client)

    tracer.flush()

    assert client.flush_count == 1


def test_factory_is_noop_unless_explicitly_enabled_and_configured() -> None:
    client = FakeLangfuseClient()

    assert isinstance(create_tracer(), NoopTracer)
    assert isinstance(create_tracer(enabled=True), NoopTracer)
    assert isinstance(
        create_tracer(
            enabled=True,
            public_key="public",
            secret_key=None,
        ),
        NoopTracer,
    )
    assert isinstance(create_tracer(enabled=False, client=client), NoopTracer)


def test_factory_accepts_injected_configured_client_without_network() -> None:
    client = FakeLangfuseClient()

    tracer = create_tracer(enabled=True, client=client)

    assert isinstance(tracer, LangfuseTracer)
    with tracer.span("validate_schema"):
        pass
    assert client.starts == [{"name": "validate_schema", "as_type": "span"}]


def test_factory_lazily_constructs_langfuse_4_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeLangfuseClient()
    constructor_calls: list[dict[str, object]] = []

    def constructor(**kwargs: object) -> FakeLangfuseClient:
        constructor_calls.append(kwargs)
        return client

    module = SimpleNamespace(Langfuse=constructor)
    monkeypatch.setattr(tracing_module, "import_module", lambda _name: module)

    tracer = create_tracer(
        enabled=True,
        public_key="pk-test",
        secret_key="sk-test",
        base_url="https://langfuse.example.test",
    )

    assert isinstance(tracer, LangfuseTracer)
    assert constructor_calls == [
        {
            "public_key": "pk-test",
            "secret_key": "sk-test",
            "base_url": "https://langfuse.example.test",
        }
    ]
