"""Lane C: Langfuse tracing. One trace per investigation; query spans (emitted inside
`data.client.run_query`) nest under it automatically via OpenTelemetry context.

The trace is a scored deliverable ("no trace, no credit"). Degrades to a no-op if Langfuse
keys are unset so the pipeline still runs locally.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass

from config import LANGFUSE
from config import config as _config
from obs import langfuse

log = logging.getLogger(__name__)


def _browser_url(url: str | None) -> str | None:
    """Rewrite the SDK's internal ingestion host to the browser-facing one.

    get_trace_url() bakes in LANGFUSE["host"], which in Docker is langfuse-web:3000 — a name the
    host browser can't resolve, so "Open trace" would dead-link. Swap it for public_host
    (localhost:3000). No-op on a host venv run, where the two are equal.
    """
    if url and LANGFUSE["host"] != LANGFUSE["public_host"]:
        return url.replace(LANGFUSE["host"], LANGFUSE["public_host"], 1)
    return url


@dataclass(frozen=True)
class Trace:
    """Handle for one investigation's trace.

    `trace_id` is persisted alongside the bundle because POST /investigate and
    POST /narrate/{id} are separate HTTP calls: narration must attach its generation span to
    the trace the investigation already opened, or the SQL steps and the LLM call show up as
    two unrelated traces and the reasoning becomes unreadable.

    `url` is what a judge clicks. Both are None when tracing is disabled.
    """
    trace_id: str | None = None
    url: str | None = None

    @property
    def enabled(self) -> bool:
        return self.trace_id is not None


@contextmanager
def investigation_trace(
    investigation_id: str, metric: str, session_id: str | None = None
):
    """Open one trace per investigation. Yields a `Trace` (inert when tracing is disabled).

    Every `run_query` call made inside this context becomes a child span of this trace, and the
    session_id is propagated to the root span and all child spans so related investigations group
    under one session in Langfuse. Falls back to investigation_id when no session_id is given.
    """
    lf = langfuse()
    if lf is None:
        yield Trace()
        return

    from langfuse import propagate_attributes

    session_id = session_id or investigation_id
    with propagate_attributes(session_id=session_id, trace_name=f"investigation:{metric}",
                              tags=[metric]):
        with lf.start_as_current_observation(
            name=f"investigation:{metric}", as_type="span"
        ) as root:
            root.update(
                input={
                    "investigation_id": investigation_id,
                    "metric": metric,
                    "session_id": session_id,
                }
            )
            trace_id = lf.get_current_trace_id()
            try:
                yield Trace(trace_id=trace_id, url=_browser_url(lf.get_trace_url(trace_id=trace_id)))
            finally:
                # Publish LAST, after the investigation's query spans exist, and against the
                # ROOT span explicitly. Two things bit here: publishing up front was undone by
                # child spans rewriting the trace record, and the client-level
                # set_current_trace_as_public() resolves "current" to whichever span is active
                # rather than the root, so it worked on a bare trace and silently no-opped on a
                # real one with 37 observations.
                _publish(root)
                lf.flush()


def _publish(root) -> None:
    """Make the trace readable without a Langfuse login, when configured.

    A trace URL is only worth putting in a submission if the person receiving it can open it.
    Without this, a judge following the link is asked to sign in, signs up, lands in their own
    empty organisation, and gets "You do not have access to this trace" - the evidence present
    and unreachable, which scores the same as not having it.

    Called with the ROOT span, not the client: the client-level
    `set_current_trace_as_public()` targets whichever span is currently active, which is not
    the root once query spans exist.

    Publishing is irreversible per Langfuse, so it stays opt-in via LANGFUSE_PUBLISH_TRACES and
    is only appropriate for a demo dataset. Never enable it against real customer data.
    """
    if not LANGFUSE.get("publish_traces"):
        return
    try:
        root.set_trace_as_public()
    except Exception as exc:  # noqa: BLE001 - an unpublished trace is worse than a failed run
        log.warning("Could not publish trace: %s", exc)


@contextmanager
def narration_span(trace_id: str | None, metric: str):
    """Attach the LLM generation to the trace the investigation already opened.

    POST /investigate and POST /narrate/{id} are separate HTTP calls, so without the stored
    trace_id the narration would start its own trace and a judge would see the SQL steps and
    the LLM call as two unrelated investigations.

    Yields the span (or None when tracing is off) so the caller can attach the prompt, the
    prose and the guardrail verdict. Reattachment is attempted defensively: if the installed
    Langfuse SDK does not accept an explicit trace context, we fall back to an unparented span
    rather than losing the narration entirely.
    """
    lf = langfuse()
    if lf is None:
        yield None
        return

    kwargs = {"name": f"narrate:{metric}", "as_type": "generation"}
    try:
        cm = (lf.start_as_current_observation(trace_context={"trace_id": trace_id}, **kwargs)
              if trace_id else lf.start_as_current_observation(**kwargs))
    except TypeError:  # SDK without trace_context support
        cm = lf.start_as_current_observation(**kwargs)

    with cm as span:
        try:
            yield span
        finally:
            lf.flush()


_TRACING = _config()["tracing"]

# Canonical phase names — the judge-facing vocabulary, defined once.
PHASES = {
    "detect": "detect",
    "decompose": "decompose",
    "drilldown": "drilldown",
    "depth": "depth-{depth}:{dim}",
    "ruled_out": "ruled-out",
}


class Phase:
    """Handle yielded by phase(). verdict() writes the decision (and its numbers) as span output."""

    def __init__(self, span=None):
        self._span = span

    @property
    def enabled(self) -> bool:
        return self._span is not None

    def verdict(self, **kw) -> None:
        if self._span is not None:
            self._span.update(output=kw)

    def rename(self, name: str) -> None:
        if self._span is not None:
            self._span.update(name=name)


@contextmanager
def phase(name: str, input: dict | None = None):
    """One investigation phase as a nested Langfuse span.

    Nests under the current OTEL context (root trace or an outer phase), so run_query spans
    land inside the innermost phase automatically. No Langfuse client or no ACTIVE trace =>
    inert Phase — the guard that keeps untraced calls (dev console, benchmarks) orphan-free.
    Flushes on exit when tracing.live_flush, so spans appear in the UI mid-investigation.
    """
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        yield Phase()
        return

    try:
        with lf.start_as_current_observation(name=name, as_type="span") as span:
            if input is not None:
                span.update(input=input)
            yield Phase(span)
    finally:
        if _TRACING["live_flush"]:
            lf.flush()


def score_trace(name: str, value, data_type: str) -> None:
    """Attach a Langfuse score to the current trace — shows as a trace-list column."""
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        return
    lf.score_current_trace(name=name, value=value, data_type=data_type)


def stamp_trace_verdict(bundle) -> None:
    """Write the investigation's conclusion onto the root trace, so the judge sees the verdict
    in the trace LIST before opening anything."""
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        return
    lf.set_current_trace_io(output={
        "detected": bundle.anomaly.detected,
        "primary_factor": bundle.factor_decomposition.primary_factor,
        "localized_segment": bundle.localized_segment,
        "score": bundle.anomaly.score,
        "pct_delta": bundle.anomaly.pct_delta,
    })
    score_trace("anomaly_score", bundle.anomaly.score, "NUMERIC")
