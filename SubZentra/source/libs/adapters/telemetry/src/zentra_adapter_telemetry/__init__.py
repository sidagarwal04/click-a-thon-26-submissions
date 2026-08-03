"""ZentraOS OpenTelemetry adapter"""

from .metrics import SAFE_DIMENSIONS
from .tracing import (
    SAFE_ATTRIBUTES,
    TelemetrySettings,
    configure_telemetry,
    correlate_investigation,
    correlate_tenant,
    current_trace_ids,
    record_citation_resolution,
    record_evidence_deletion,
    record_insight_execution,
    record_publication_decision,
)

__all__ = [
    "SAFE_ATTRIBUTES",
    "SAFE_DIMENSIONS",
    "TelemetrySettings",
    "configure_telemetry",
    "correlate_investigation",
    "correlate_tenant",
    "current_trace_ids",
    "record_citation_resolution",
    "record_evidence_deletion",
    "record_insight_execution",
    "record_publication_decision",
]
