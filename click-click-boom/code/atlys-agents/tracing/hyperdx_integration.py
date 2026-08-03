"""ClickStack OpenTelemetry integration for centralized logging and tracing.

This module adds ClickStack (local OTEL collector) as an additional exporter to Langfuse's
existing OpenTelemetry setup, so all Langfuse traces are automatically sent to ClickStack
(and then to ClickHouse Cloud) with the same trace IDs.
"""
import logging
import os
from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from dotenv import load_dotenv

load_dotenv()

_initialized = False


def init_hyperdx():
    """Initialize ClickStack OpenTelemetry integration (optional).

    This adds ClickStack OTEL collector as an additional span processor to the existing
    (Langfuse) TracerProvider, so all Langfuse traces are automatically sent to ClickStack.

    If ClickStack is not configured or the collector is not running, this fails silently
    and agents continue to work normally with just Langfuse tracing.

    Call this once at the start of your application, AFTER Langfuse has been imported.
    """
    global _initialized
    if _initialized:
        return

    try:
        # Get the existing tracer provider (set by Langfuse)
        tracer_provider = trace.get_tracer_provider()

        # If no tracer provider exists yet, we can't proceed
        # (Langfuse needs to be imported first)
        if not hasattr(tracer_provider, 'add_span_processor'):
            logging.debug("No TracerProvider found - ClickStack integration skipped")
            return

        # Configure OTLP exporter for ClickStack (local collector on port 4317)
        otlp_exporter = OTLPSpanExporter(
            endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
            insecure=True,  # Local collector doesn't use TLS
        )

        # Add ClickStack span processor to existing provider
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Instrument Python logging to send logs to ClickStack. Imported here, not at
        # module level: opentelemetry-instrumentation-logging is a separate optional
        # package from the core opentelemetry-instrumentation one, and this whole
        # module's contract (stated above) is "ClickStack is optional, fails silently
        # if not configured" — a module-level import would instead hard-crash every
        # importer of this module (langfuse_wrapper -> orchestrator.pipeline, i.e. the
        # entire agent pipeline) if this one optional package were ever missing, which
        # it was: it's not in requirements.txt and wasn't installed in this venv,
        # meaning `from orchestrator import ingest_spec` raised ModuleNotFoundError on
        # a clean checkout — caught by actually trying the import, not assumed.
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=True)

        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        _initialized = True
        logging.info("ClickStack OTEL collector initialized - traces will flow to ClickHouse Cloud")

    except Exception as e:
        # ClickStack is optional - if it fails, just log a warning and continue
        logging.warning(f"ClickStack initialization failed (non-critical): {e}")
        logging.info("Agents will continue with Langfuse tracing only")


def get_tracer(name: str = "atlys"):
    """Get an OpenTelemetry tracer for creating spans."""
    return trace.get_tracer(name)


def log_to_hyperdx(level: str, message: str, **attributes):
    """Log a message to ClickStack with optional attributes (optional).

    If ClickStack is not initialized, this silently does nothing and agents continue normally.

    Args:
        level: Log level (info, warning, error, debug)
        message: Log message
        **attributes: Additional key-value pairs to attach to the log
    """
    try:
        logger = logging.getLogger("atlys")
        log_func = getattr(logger, level.lower(), logger.info)

        # Add attributes as extra fields
        log_func(message, extra=attributes)
    except Exception:
        # ClickStack logging is optional - silently ignore failures
        pass
