"""Langfuse + OpenTelemetry setup for investigation traces."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from clickathon.config import Settings, get_settings

logger = logging.getLogger(__name__)

_langfuse = None
_otel_ready = False


def init_telemetry(settings: Settings | None = None) -> None:
    global _langfuse, _otel_ready
    s = settings or get_settings()

    if s.langfuse_public_key and s.langfuse_secret_key and _langfuse is None:
        try:
            from langfuse import Langfuse

            _langfuse = Langfuse(
                public_key=s.langfuse_public_key,
                secret_key=s.langfuse_secret_key,
                host=s.langfuse_base_url,
            )
            logger.info("Langfuse client initialized (%s)", s.langfuse_base_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Langfuse init failed: %s", exc)

    if s.otel_exporter_otlp_endpoint and not _otel_ready:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            endpoint = s.otel_exporter_otlp_endpoint.rstrip("/")
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint}/v1/traces"

            headers: dict[str, str] = {}
            if s.hyperdx_api_key:
                # ClickStack collector expects raw team API key (not Bearer)
                headers["authorization"] = s.hyperdx_api_key

            current = trace.get_tracer_provider()
            if type(current).__name__ == "TracerProvider":
                _otel_ready = True
            else:
                provider = TracerProvider(
                    resource=Resource.create({"service.name": s.otel_service_name})
                )
                provider.add_span_processor(
                    BatchSpanProcessor(
                        OTLPSpanExporter(endpoint=endpoint, headers=headers or None)
                    )
                )
                trace.set_tracer_provider(provider)
                _otel_ready = True
                logger.info("OTel exporter → %s", endpoint)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OTel init failed: %s", exc)


def get_langfuse():
    return _langfuse


def get_tracer():
    from opentelemetry import trace

    return trace.get_tracer("clickathon.rca")


@contextmanager
def investigation_span(name: str, *, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
    """Nested Langfuse + OTel span for one investigation step."""
    init_telemetry()
    meta = metadata or {}
    lf = get_langfuse()
    tracer = get_tracer()

    lf_cm = None
    if lf is not None:
        try:
            if hasattr(lf, "start_as_current_observation"):
                lf_cm = lf.start_as_current_observation(as_type="span", name=name, metadata=meta)
            elif hasattr(lf, "start_span"):
                span = lf.start_span(name=name, metadata=meta)
                lf_cm = _SpanWrap(span)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Langfuse span skipped: %s", exc)

    with tracer.start_as_current_span(name) as otel_span:
        for k, v in meta.items():
            try:
                otel_span.set_attribute(f"rca.{k}", str(v)[:256])
            except Exception:  # noqa: BLE001
                pass
        if lf_cm is not None:
            with lf_cm as lf_span:
                yield lf_span or otel_span
        else:
            yield otel_span


@contextmanager
def clickhouse_query_span(
    sql: str,
    *,
    parameters: dict[str, Any] | None = None,
    database: str = "",
) -> Iterator[Any]:
    """Langfuse + OTel span that records the SQL text and result stats."""
    init_telemetry()
    lf = get_langfuse()
    tracer = get_tracer()
    params = parameters or {}
    # Avoid logging secrets; parameters are usually dates/ids
    safe_params = {k: str(v)[:120] for k, v in params.items()}
    inp = {
        "sql": (sql or "")[:8000],
        "parameters": safe_params,
        "database": database,
    }
    meta = {"db.system": "clickhouse", "db.statement_preview": (sql or "")[:200]}

    lf_cm = None
    if lf is not None:
        try:
            lf_cm = lf.start_as_current_observation(
                as_type="span",
                name="clickhouse.query",
                metadata=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Langfuse CH span skipped: %s", exc)

    with tracer.start_as_current_span("clickhouse.query") as otel_span:
        otel_span.set_attribute("db.system", "clickhouse")
        otel_span.set_attribute("db.statement", (sql or "")[:1024])
        if database:
            otel_span.set_attribute("db.name", database)
        if lf_cm is not None:
            with lf_cm as lf_span:
                if lf_span is not None and hasattr(lf_span, "update"):
                    try:
                        lf_span.update(input=inp, metadata=meta)
                    except Exception:  # noqa: BLE001
                        pass
                yield lf_span or otel_span
        else:
            yield otel_span


def finish_query_span(
    span: Any,
    *,
    n_rows: int | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    """Attach query result stats to a clickhouse.query span."""
    out: dict[str, Any] = {}
    if n_rows is not None:
        out["n_rows"] = n_rows
    if duration_ms is not None:
        out["duration_ms"] = round(duration_ms, 2)
    if error:
        out["error"] = error[:500]
    if span is not None and hasattr(span, "update") and out:
        try:
            span.update(output=out)
        except Exception:  # noqa: BLE001
            pass
    # OTel attributes
    try:
        if n_rows is not None:
            span.set_attribute("db.row_count", int(n_rows))
        if duration_ms is not None:
            span.set_attribute("db.duration_ms", float(duration_ms))
        if error:
            span.set_attribute("error", True)
            span.set_attribute("error.message", error[:256])
    except Exception:  # noqa: BLE001
        pass


class _SpanWrap:
    def __init__(self, span: Any) -> None:
        self.span = span

    def __enter__(self) -> Any:
        return self.span

    def __exit__(self, *args: Any) -> None:
        end = getattr(self.span, "end", None)
        if callable(end):
            end()


def flush_telemetry() -> None:
    lf = get_langfuse()
    if lf is not None and hasattr(lf, "flush"):
        try:
            lf.flush()
        except Exception:  # noqa: BLE001
            pass
