"""Small, optional tracing abstraction backed by Langfuse.

The adapter deliberately has no knowledge of feature files or event payloads.  It
only records values a caller explicitly supplies, so raw specs and NDJSON are not
captured as an accidental side effect of tracing.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from importlib import import_module
from typing import Literal, Protocol, cast

ObservationType = Literal[
    "span",
    "generation",
    "agent",
    "tool",
    "chain",
    "retriever",
    "embedding",
    "evaluator",
    "guardrail",
]
SpanLevel = Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"]


class TraceSpan(Protocol):
    """Observation surface shared by real and no-op tracers."""

    @property
    def trace_id(self) -> str | None:
        """Identifier of the containing trace, when tracing is enabled."""
        ...

    def update(
        self,
        *,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
        level: SpanLevel | None = None,
        status: str | None = None,
    ) -> None:
        """Attach an explicit result or compact metadata to this observation."""
        ...


class Tracer(Protocol):
    """Tracing contract used by API, MCP, and CLI entry points."""

    def span(
        self,
        name: str,
        *,
        input: object | None = None,
        as_type: ObservationType = "span",
    ) -> AbstractContextManager[TraceSpan]:
        """Start an observation that is current for the duration of the context."""
        ...

    def flush(self) -> None:
        """Send buffered observations before a short-lived process exits."""
        ...


class LangfuseObservation(Protocol):
    """Subset of a Langfuse observation consumed by this adapter."""

    trace_id: str

    def update(self, **kwargs: object) -> object:
        """Update observation fields supported by the Langfuse SDK."""
        ...


class LangfuseClient(Protocol):
    """Subset of the Langfuse 4 client consumed by this adapter."""

    def start_as_current_observation(
        self, **kwargs: object
    ) -> AbstractContextManager[LangfuseObservation]:
        """Start an observation and propagate it through the current context."""
        ...

    def flush(self) -> None:
        """Flush pending telemetry."""
        ...


class _LangfuseConstructor(Protocol):
    def __call__(self, **kwargs: object) -> LangfuseClient: ...


class _NoopSpan:
    @property
    def trace_id(self) -> None:
        return None

    def update(
        self,
        *,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
        level: SpanLevel | None = None,
        status: str | None = None,
    ) -> None:
        return None


_NOOP_SPAN = _NoopSpan()


class NoopTracer:
    """Tracer used unless remote tracing has been deliberately configured."""

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input: object | None = None,
        as_type: ObservationType = "span",
    ) -> Iterator[TraceSpan]:
        yield _NOOP_SPAN

    def flush(self) -> None:
        return None


class _LangfuseTraceSpan:
    def __init__(self, observation: LangfuseObservation) -> None:
        self._observation = observation

    @property
    def trace_id(self) -> str:
        return self._observation.trace_id

    def update(
        self,
        *,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
        level: SpanLevel | None = None,
        status: str | None = None,
    ) -> None:
        fields: dict[str, object] = {}
        if output is not None:
            fields["output"] = output
        if metadata is not None:
            fields["metadata"] = dict(metadata)
        if level is not None:
            fields["level"] = level
        if status is not None:
            fields["status_message"] = status
        if fields:
            self._observation.update(**fields)


class LangfuseTracer:
    """Trace pipeline stages through an injected Langfuse-compatible client."""

    def __init__(self, client: LangfuseClient) -> None:
        self._client = client

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input: object | None = None,
        as_type: ObservationType = "span",
    ) -> Iterator[TraceSpan]:
        fields: dict[str, object] = {"name": name, "as_type": as_type}
        if input is not None:
            fields["input"] = input

        with self._client.start_as_current_observation(**fields) as observation:
            yield _LangfuseTraceSpan(observation)

    def flush(self) -> None:
        self._client.flush()


def _configured(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _create_langfuse_client(
    *,
    public_key: str,
    secret_key: str,
    base_url: str | None,
) -> LangfuseClient:
    module = import_module("langfuse")
    constructor = cast(_LangfuseConstructor, module.Langfuse)
    fields: dict[str, object] = {
        "public_key": public_key,
        "secret_key": secret_key,
    }
    if _configured(base_url):
        fields["base_url"] = base_url
    return constructor(**fields)


def create_tracer(
    *,
    enabled: bool = False,
    public_key: str | None = None,
    secret_key: str | None = None,
    base_url: str | None = None,
    client: LangfuseClient | None = None,
) -> Tracer:
    """Build an opt-in tracer, falling back safely when it is unconfigured.

    An injected client represents an already-configured Langfuse connection and is
    primarily useful for application lifecycle wiring and network-free tests.
    """

    if not enabled:
        return NoopTracer()
    if client is not None:
        return LangfuseTracer(client)
    if not (_configured(public_key) and _configured(secret_key)):
        return NoopTracer()

    return LangfuseTracer(
        _create_langfuse_client(
            public_key=cast(str, public_key),
            secret_key=cast(str, secret_key),
            base_url=base_url,
        )
    )


__all__ = [
    "LangfuseClient",
    "LangfuseTracer",
    "NoopTracer",
    "ObservationType",
    "SpanLevel",
    "TraceSpan",
    "Tracer",
    "create_tracer",
]
