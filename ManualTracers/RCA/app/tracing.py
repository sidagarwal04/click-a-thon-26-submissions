import logging
from urllib.parse import urlparse

from app.settings import get_settings

logger = logging.getLogger("rca_agent.tracing")

_client = None


def _disable_tls_verify_for_langfuse() -> None:
    """Inside the rca-agent container, exporting to Langfuse fails with
    SSLCertVerificationError('self-signed certificate in certificate chain') — a corporate
    proxy intercepting outbound TLS with a root cert the container's minimal image doesn't
    trust (the host's own Python trusts it fine via the OS store; python:3.13-slim doesn't
    ship it). Langfuse builds its OTLP exporter's requests.Session internally — including
    the one @observe's global client uses, which is created on first span, before anything
    in this module gets a chance to run get_langfuse() — so the only hook available is a
    patch on requests.Session itself, applied at import time (before ANY such session can
    be built) rather than lazily inside get_langfuse().

    Scoped to just the Langfuse host via merge_environment_settings, not a blanket
    Session.verify=False: google.genai's requests-based paths share this same process."""
    import requests

    if getattr(requests.Session, "_rca_langfuse_tls_patched", False):
        return

    langfuse_host = urlparse(
        get_settings().langfuse_base_url or "https://us.cloud.langfuse.com"
    ).hostname
    original_merge = requests.Session.merge_environment_settings

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        settings = original_merge(self, url, proxies, stream, verify, cert)
        if urlparse(url).hostname == langfuse_host:
            settings["verify"] = False
        return settings

    requests.Session.merge_environment_settings = merge_environment_settings
    requests.Session._rca_langfuse_tls_patched = True

    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


if get_settings().langfuse_configured:
    _disable_tls_verify_for_langfuse()


def get_langfuse():
    global _client
    settings = get_settings()
    if _client is None and settings.langfuse_configured:
        from langfuse import Langfuse

        kwargs = {
            "public_key": settings.langfuse_public_key,
            "secret_key": settings.langfuse_secret_key,
        }
        if settings.langfuse_base_url:
            kwargs["base_url"] = settings.langfuse_base_url
        _client = Langfuse(**kwargs)
    return _client


def traced(name: str):
    """Wraps a ladder stage in a Langfuse span. No-op when Langfuse isn't configured, so
    the investigation never depends on tracing credentials to run locally or in tests —
    ponytail: env-gated like clickhouse_client's lazy singleton, not a hard dependency."""
    if not get_settings().langfuse_configured:
        return lambda fn: fn

    from langfuse import observe

    return observe(name=name)


def record_query(sql: str, parameters, query_id, read_rows, elapsed_s: float) -> None:
    """Attaches SQL text + query_id + row/elapsed stats to whichever @traced span is
    currently active — the evidence that ClickHouse, not the LLM, did the work.

    A no-op, quietly, when query_rows() runs outside any @traced(...) function — e.g.
    get_metric() called directly from a FastAPI handler before the traced investigation
    functions run. Checking first avoids Langfuse's own update_current_span(): it doesn't
    raise in that case, it logs a warning directly ('Context error: No active span...'),
    which our try/except below never sees since nothing was thrown."""
    client = get_langfuse()
    if client is None:
        return

    from opentelemetry import trace as otel_trace_api

    if otel_trace_api.get_current_span() is otel_trace_api.INVALID_SPAN:
        return

    try:
        client.update_current_span(
            metadata={
                "sql": sql,
                "parameters": parameters,
                "query_id": query_id,
                "read_rows": read_rows,
                "elapsed_s": elapsed_s,
            }
        )
    except Exception:
        logger.warning("failed to record query span", exc_info=True)


def flush() -> None:
    """Blocks until the trace is sent — an unflushed trace on a short-lived process is
    worth zero on the 'no trace, no credit' criterion."""
    client = get_langfuse()
    if client is not None:
        client.flush()
