"""Shared Langfuse tracing wrapper with HyperDX integration. Every agent action logs
through this — nobody calls the Langfuse SDK directly.

Verified against langfuse==4.14.2's real API by introspection, not docs/memory — the
v4 SDK is OpenTelemetry-based and has NO `Langfuse.trace()` / `.span()` methods (that
was the v2/v3 API). The real primitives are:
  - `get_client()`            — singleton reading LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST from env
  - `client.start_as_current_observation(name=..., as_type="span", ...)` — a context
    manager; nesting is automatic OTel context propagation (create one inside another's
    `with` block and it becomes a child span, no manual parent-linking needed)
  - `propagate_attributes(tags=..., metadata=..., ...)` — module-level context manager
    that sets trace-level tags/metadata on the current + all subsequently-created spans
  - `client.get_trace_url(trace_id=...)` — the root span's `.trace_id` attribute gives you this

HyperDX Integration:
  - All logs and traces are also sent to HyperDX for centralized observability
  - Langfuse traces are cross-referenced in HyperDX via trace IDs

Usage:

    from tracing import traced_run

    with traced_run(agent="instrumentation", spec="express_checkout") as run:
        run.log(step="propose_ordering_key", input=spec_text, output=ddl, reasoning="...")

        with run.span("context_review", revision=1):
            ...  # nested sub-steps for a multi-part step, e.g. an agent turn with tool calls

        trace_url = run.url   # store this on the agent_meta row you just wrote
"""
import contextlib
import json
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from langfuse import get_client, propagate_attributes

load_dotenv()

# Import ClickStack integration (but don't initialize yet - we'll do it after first Langfuse call)
from .hyperdx_integration import init_hyperdx, get_tracer, log_to_hyperdx
from dashboard.emitter import emit_event
from agent_meta.db import get_client as get_ch_client

_clickstack_initialized = False


def _stringify(v) -> str:
    """input/output/usage/metadata are a mix of raw strings (tool outputs are
    already strings) and Python objects (payloads, usage dicts) -- store both
    as plain strings in trace_events (a String column, not JSON-typed) without
    double-encoding an already-string value."""
    if v is None:
        return ""
    return v if isinstance(v, str) else json.dumps(v, default=str)


_TRACE_EVENTS_COLS = ["ts", "trace_id", "trace_url", "agent", "spec_name", "step",
                      "event", "kind", "input", "output", "reasoning", "usage", "metadata"]

# Flush periodically DURING a run, not only once at the very end. Found the
# hard way: two real runs that both ended in an exception (exhausted rework
# revisions) have ZERO persisted trace_events despite genuinely running for
# 10+ minutes each -- the single end-of-run bulk insert is all-or-nothing, so
# if it fails for ANY reason (or the process is killed hard enough to skip
# Python's `finally`), the ENTIRE trace is lost, not just the tail. Flushing
# every _FLUSH_BATCH_SIZE events caps how much a single failure can cost.
_FLUSH_BATCH_SIZE = 25


def _rows_from_events(events: list[dict]) -> list[list]:
    return [[
        datetime.fromtimestamp(e.get("ts", time.time()), tz=timezone.utc),
        e.get("trace_id", ""), e.get("trace_url", ""), e.get("agent", ""),
        e.get("spec", ""), e.get("step", ""), e.get("event", ""), e.get("kind", ""),
        _stringify(e.get("input")), _stringify(e.get("output")),
        e.get("reasoning") or "", _stringify(e.get("usage")), _stringify(e.get("metadata")),
    ] for e in events]


def _flush_trace_events(events: list[dict]) -> None:
    """Bulk INSERT for a batch of events -- one INSERT per BATCH, not per
    event (per-event inserts against ClickHouse are exactly the anti-pattern
    this pipeline itself flags to the proposer). Best-effort: a failure here
    must never take down the pipeline run itself. Falls back to one-row-at-a-
    time on a bulk failure so a single malformed event doesn't sink the whole
    batch -- confirmed a 300-row synthetic batch inserts cleanly in the common
    case, so this fallback is specifically for the rare bad-row scenario."""
    if not events:
        return
    try:
        client = get_ch_client(database="agent_meta")
        client.insert("trace_events", _rows_from_events(events), column_names=_TRACE_EVENTS_COLS)
    except Exception:
        logging.getLogger(__name__).warning(
            "bulk trace_events insert failed for %d rows, falling back to per-row", len(events), exc_info=True,
        )
        client = get_ch_client(database="agent_meta")
        for row in _rows_from_events(events):
            try:
                client.insert("trace_events", [row], column_names=_TRACE_EVENTS_COLS)
            except Exception:
                logging.getLogger(__name__).exception("failed to persist one trace_event row (skipped)")


def _step_kind(step: str) -> str:
    """Classifies a step name for the dashboard's UI (icon/color per row), purely
    cosmetic — matches the naming convention orchestrator/agent_io.py's
    _call_json_agent already uses (`{step}_generation`, `{step}_tool[i]_{name}`,
    `{step}_reasoning[turnN]` — the last logged LIVE per turn during the
    tool-calling loop, not batched at the end).

    "executed"/"context_updated" (orchestrator/pipeline.py's real-DDL-executed
    and chronicler-sections-written summaries) used to fall through to plain
    "log" -- which the dashboard's VISIBLE_KINDS filter drops entirely, so
    what actually got created in ClickHouse and what context sections got
    written were silently invisible in the trace view. Distinct kinds so the
    frontend can show them as their own named, structured sections instead."""
    if "_tool[" in step:
        return "tool_call"
    if "_reasoning[" in step:
        return "reasoning"
    if step.endswith("_generation"):
        return "generation"
    if step == "approved":
        return "approved"
    if step == "executed":
        return "execution"
    if step == "context_updated":
        return "context_update"
    return "log"


class Run:
    """Wraps one Langfuse trace for a full pipeline run (e.g. one spec's
    propose -> review -> [rework] -> test -> execute -> commit sequence)."""

    def __init__(self, client, root_span, agent: str = "", spec: str = ""):
        self._client = client
        self._root_span = root_span
        self.agent = agent
        self.spec = spec
        self._events: list[dict] = []  # ALL events this run has emitted so far
        self._flushed_count = 0  # how many of _events are already durably in trace_events

    @property
    def trace_id(self) -> str:
        return self._root_span.trace_id

    @property
    def url(self) -> str:
        return self._client.get_trace_url(trace_id=self._root_span.trace_id)

    def _record(self, event: dict) -> None:
        """Buffer one event and flush every _FLUSH_BATCH_SIZE, instead of only
        at traced_run()'s very end -- see _flush_trace_events' docstring for
        why (two real runs lost their entire trace to a single end-of-run
        flush that never landed)."""
        self._events.append(event)
        pending = len(self._events) - self._flushed_count
        if pending >= _FLUSH_BATCH_SIZE:
            _flush_trace_events(self._events[self._flushed_count:])
            self._flushed_count = len(self._events)

    def log(self, step: str, input=None, output=None, reasoning: str = None, usage: dict = None, **metadata):
        """One-shot child span for a single call/decision with no sub-steps of its own."""
        meta = dict(metadata)
        if reasoning is not None:
            meta["reasoning"] = reasoning

        # Log to ClickStack
        log_to_hyperdx(
            "info",
            f"[{step}] {reasoning or step}",
            trace_id=self.trace_id,
            langfuse_url=self.url,
            **meta
        )

        # Log to realtime dashboard (best-effort, see dashboard/emitter.py) and
        # buffer for the durable batch insert at trace end (tracing/langfuse_wrapper.py's
        # _flush_trace_events) -- built once, with an explicit ts, so the live
        # POST and the persisted row agree on exactly when this happened.
        event = {
            "event": "log",
            "kind": _step_kind(step),
            "trace_id": self.trace_id,
            "trace_url": self.url,
            "agent": self.agent,
            "spec": self.spec,
            "step": step,
            "input": input,
            "output": output,
            "reasoning": reasoning,
            "usage": usage,
            "metadata": metadata,
            "ts": time.time(),
        }
        emit_event(event)
        self._record(event)

        # Use "generation" type if usage data is provided (LLM call), otherwise "span"
        observation_type = "generation" if usage else "span"
        kwargs = {
            "name": step,
            "as_type": observation_type,
            "input": input,
            "output": output,
            "metadata": meta or None,
        }
        if usage:
            # Langfuse v4 expects usage_details parameter (not "usage")
            # The format should match: {input: int, output: int, total: int}
            kwargs["usage_details"] = usage

        with self._client.start_as_current_observation(**kwargs):
            pass

    @contextlib.contextmanager
    def span(self, name: str, **metadata):
        """Nested span for a step that itself has multiple sub-actions (e.g. an
        agent turn that made several tool calls) — log those sub-steps onto the
        yielded span via further run.log(...) calls made while inside this `with`."""
        # Log span start to ClickStack
        log_to_hyperdx(
            "info",
            f"[span:start] {name}",
            trace_id=self.trace_id,
            langfuse_url=self.url,
            **metadata
        )
        span_start_event = {
            "event": "span_start", "kind": "span",
            "trace_id": self.trace_id, "trace_url": self.url,
            "agent": self.agent, "spec": self.spec,
            "step": name, "metadata": metadata, "ts": time.time(),
        }
        emit_event(span_start_event)
        self._record(span_start_event)

        with self._client.start_as_current_observation(
            name=name, as_type="span", metadata=metadata or None
        ) as span:
            try:
                yield span
            finally:
                # Log span end to ClickStack
                log_to_hyperdx(
                    "info",
                    f"[span:end] {name}",
                    trace_id=self.trace_id,
                    langfuse_url=self.url,
                    **metadata
                )
                span_end_event = {
                    "event": "span_end", "kind": "span",
                    "trace_id": self.trace_id, "trace_url": self.url,
                    "agent": self.agent, "spec": self.spec,
                    "step": name, "metadata": metadata, "ts": time.time(),
                }
                emit_event(span_end_event)
                self._record(span_end_event)


@contextlib.contextmanager
def traced_run(agent: str, spec: str, **extra_tags):
    """Opens one Langfuse trace. `agent` in {'instrumentation','analytics','context','pipeline'},
    `spec` is the feature-spec slug (e.g. 'express_checkout', 'unseen'). Extra kwargs become
    additional tags, e.g. traced_run(agent="instrumentation", spec="unseen", revision=2)."""
    global _clickstack_initialized

    client = get_client()

    # Initialize ClickStack after Langfuse's TracerProvider is set up
    if not _clickstack_initialized:
        init_hyperdx()
        _clickstack_initialized = True

    tags = [
        f"agent:{agent}",
        f"spec:{spec}",
        f"run:{datetime.now(timezone.utc):%Y-%m-%d}",
    ]
    tags += [f"{k}:{v}" for k, v in extra_tags.items()]

    with client.start_as_current_observation(name=f"{agent}:{spec}", as_type="span") as root_span:
        with propagate_attributes(tags=tags, metadata={"agent": agent, "spec": spec, **extra_tags}):
            run = Run(client, root_span, agent=agent, spec=spec)

            # Log trace start to ClickStack
            log_to_hyperdx(
                "info",
                f"[trace:start] {agent}:{spec}",
                trace_id=run.trace_id,
                langfuse_url=run.url,
                agent=agent,
                spec=spec,
                **extra_tags
            )
            trace_start_event = {
                "event": "trace_start", "kind": "trace",
                "trace_id": run.trace_id, "trace_url": run.url,
                "agent": agent, "spec": spec, "metadata": extra_tags, "ts": time.time(),
            }
            emit_event(trace_start_event)
            run._record(trace_start_event)

            try:
                yield run
            finally:
                # Log trace end to ClickStack
                log_to_hyperdx(
                    "info",
                    f"[trace:end] {agent}:{spec}",
                    trace_id=run.trace_id,
                    langfuse_url=run.url,
                    agent=agent,
                    spec=spec,
                    **extra_tags
                )
                trace_end_event = {
                    "event": "trace_end", "kind": "trace",
                    "trace_id": run.trace_id, "trace_url": run.url,
                    "agent": agent, "spec": spec, "metadata": extra_tags, "ts": time.time(),
                }
                emit_event(trace_end_event)
                run._events.append(trace_end_event)  # append only -- flush below covers it, don't double-count via _record
                _flush_trace_events(run._events[run._flushed_count:])
                client.flush()
