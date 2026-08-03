"""Single entrypoint: run_investigation(metric, window_start, window_end).
The 7 steps from Docs/Mindmap/INVESTIGATION_ENGINE.md -- baseline -> decompose
-> rank -> drilldown (recursive) -> rule_out -> evidence -> narrate -- are
orchestrated by engine/graph.py's LangGraph StateGraph; this module owns the
Langfuse tracing/persistence wrapper around that graph run, unchanged from
before the LangGraph reapproach. Stateless -- creates a fresh Trace per call,
so this is safe to invoke concurrently from multiple API workers with no
shared mutable state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from engine.ch_client import Trace
from engine.evidence import EvidenceBundle
from engine.graph import run_graph
from engine.narrator import NarrationResult
from engine.tracing import (
    get_current_trace_url,
    log_ruled_out_events,
    traced_investigation,
)


@dataclass
class InvestigationResult:
    evidence: EvidenceBundle
    narration: NarrationResult
    langfuse_trace_url: Optional[str] = None


def run_investigation(metric: str, window_start: datetime, window_end: datetime) -> InvestigationResult:
    with traced_investigation(
        name="investigation",
        metadata={"metric": metric, "window_start": str(window_start), "window_end": str(window_end)},
    ) as lf_client:
        result = _run_investigation(metric, window_start, window_end, lf_client)
        result.langfuse_trace_url = get_current_trace_url(lf_client)
        return result


def _run_investigation(metric: str, window_start: datetime, window_end: datetime, lf_client) -> InvestigationResult:
    trace = Trace()
    # Query spans and the narrator generation are now created in REAL TIME by
    # engine/ch_client.py and engine/narrator.py respectively (true durations,
    # true parallel overlap). Replaying them here as well would double-log
    # every query, so this only adds the point-in-time rule-out events.
    evidence, narration = run_graph(metric, window_start, window_end, trace)

    log_ruled_out_events(lf_client, evidence.ruled_out)  # RuledOutEvidence already has .check/.reason/.numbers

    return InvestigationResult(evidence=evidence, narration=narration)
