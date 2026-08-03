"""In-process event bus + handler registry (ENGINEERING.md §2.4).

`EventBus.emit(event)` synchronously calls every registered handler for the
event type (in registration order), then persists the event to
`atlys.event_log`. Handlers may emit new events — they're dispatched
depth-first on the *same thread* (so the full spec.run chain unwinds before
the tool returns).

Different aggregates may be emitted concurrently on different threads; the
loop-guard stack is thread-local. Version counters and the in-memory mirror
use fine-grained locks — there is **no** global "one event at a time" lock.
Cross-request idempotency for approve/reject lives in ClickHouse CAS on
`meta.pending_runs`, not here.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from . import events as ev
from .events import Event, new_event

log = logging.getLogger("atlys.bus")

Handler = Callable[[Event], None]

# Default cap on persisted events per spec run (flood guard, §3.2 of
# docs/inspect-tab-plan.md). Overridable via constructor (settings).
DEFAULT_MAX_EVENTS_PER_RUN = 200
# Bounded in-memory mirror — the event log in ClickHouse is the source of truth.
MIRROR_MAXLEN = 2000


class EventBus:
    """Registry of event_type → [handlers] with depth-first dispatch."""

    def __init__(self, store: Any, tracer: Any = None, persist: bool = True,
                 max_events_per_run: int = DEFAULT_MAX_EVENTS_PER_RUN):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._store = store
        self._tracer = tracer
        self._persist = persist
        self.max_events_per_run = max(1, int(max_events_per_run))
        self._aggregate_versions: dict[str, int] = defaultdict(int)
        self._version_lock = threading.Lock()
        self._mirror_lock = threading.Lock()
        self._cap_lock = threading.Lock()
        self._run_counts: dict[str, int] = {}      # run key → events persisted
        self._aborted_runs: set[str] = set()       # run keys past the cap
        self._local = threading.local()
        self.emitted: deque[Event] = deque(maxlen=MIRROR_MAXLEN)  # bounded mirror

    # -- per-run flood guard (§3.2) ----------------------------------------
    @staticmethod
    def _run_key(event: Event) -> str:
        """Key an event to a spec run: payload.run_id, else trace_id.

        `tool.called` events are exempt — they are bounded by the chat tool
        budget already and carry no run_id of their own.
        """
        if event.event_type == ev.TOOL_CALLED:
            return ""
        # trace_id-first: every pipeline event in a spec run carries the run's
        # trace_id, so this gives exactly one bucket per run. (Keying run_id
        # first would split a run across two buckets — events like
        # context.checked / insight.created carry trace_id but not run_id.)
        if event.trace_id:
            return f"trace:{event.trace_id}"
        rid = (event.payload or {}).get("run_id")
        if rid:
            return f"run:{rid}"
        return ""

    def _charge_or_abort(self, event: Event) -> bool:
        """Charge one event against its run; True = still under the cap.

        When a run crosses the cap it is aborted once: a synthetic
        `run.aborted (reason=event_cap)` event is persisted so the chain shows
        *why* it stopped, and all further events for that run are persisted but
        never dispatched (persist-only mode). Keyed per run_id, not per
        aggregate — re-running the same spec cannot false-trigger a previous
        run's budget.
        """
        key = self._run_key(event)
        if not key:
            return True
        with self._cap_lock:
            if key in self._aborted_runs:
                return False
            count = self._run_counts.get(key, 0) + 1
            if count > self.max_events_per_run:
                self._aborted_runs.add(key)
                log.error(
                    "run %s exceeded %d events — aborting handler dispatch "
                    "(persist-only from here)",
                    event.payload.get("run_id") or event.trace_id,
                    self.max_events_per_run,
                )
                abort = new_event(
                    ev.RUN_ABORTED,
                    event.aggregate_id,
                    ev.ACTOR_SYSTEM,
                    payload={
                        "run_id": event.payload.get("run_id")
                        or event.trace_id
                        or "",
                        "reason": "event_cap",
                        "limit": self.max_events_per_run,
                    },
                    trace_id=event.trace_id,
                )
                try:
                    self._persist_event(abort)
                    with self._mirror_lock:
                        self.emitted.append(abort)
                except Exception:  # noqa: BLE001
                    log.exception("failed to persist run.aborted for %s", key)
                return False
            self._run_counts[key] = count
            return True

    # -- registration --

    def _dispatch_stack(self) -> list[str]:
        stack = getattr(self._local, "dispatching", None)
        if stack is None:
            stack = []
            self._local.dispatching = stack
        return stack

    # -- registration --
    def register(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)
        log.debug("registered handler %s for %s", getattr(handler, "__name__", handler), event_type)

    def register_many(self, mapping: dict[str, list[Handler]]) -> None:
        for event_type, handlers in mapping.items():
            for h in handlers:
                self.register(event_type, h)

    # -- emission --
    def emit(self, event: Event) -> None:
        """Dispatch an event to its handlers, then persist it.

        Handlers run depth-first on this thread: any event a handler emits is
        dispatched before we finish the current one (matches §2.4). Concurrent
        emits for *other* aggregates on other threads proceed in parallel.

        Flood guard: events belonging to an aborted run are persisted but never
        dispatched (persist-only mode, §3.2).
        """
        if event.version == 0:
            with self._version_lock:
                self._aggregate_versions[event.aggregate_id] += 1
                event.version = self._aggregate_versions[event.aggregate_id]

        if not self._charge_or_abort(event):
            # persist-only for this run — record the event, run no handlers
            try:
                self._persist_event(event)
            finally:
                with self._mirror_lock:
                    self.emitted.append(event)
            return

        if event.event_type not in self._handlers:
            log.debug("no handlers for %s — persisting only", event.event_type)

        stack = [event]
        dispatching = self._dispatch_stack()
        while stack:
            current = stack.pop()
            marker = f"{current.event_type}:{current.aggregate_id}"
            if marker in dispatching:
                log.warning("dispatch loop guard tripped for %s", marker)
                continue
            dispatching.append(marker)
            try:
                for handler in self._handlers.get(current.event_type, []):
                    try:
                        handler(current)
                    except Exception:
                        log.exception("handler %s failed for %s", handler.__name__, current)
                        raise
            finally:
                dispatching.pop()

            self._persist_event(current)
            with self._mirror_lock:
                self.emitted.append(current)

    def _persist_event(self, event: Event) -> None:
        if not self._persist:
            return
        span_ctx = None
        if self._tracer is not None:
            try:
                span_ctx = self._tracer.span(
                    "bus:persist",
                    event_type=event.event_type,
                    aggregate_id=event.aggregate_id,
                )
                span_ctx.__enter__()
            except Exception:  # noqa: BLE001 — never let tracing break persistence
                span_ctx = None
        try:
            row = event.as_row()
            self._store.insert(
                "atlys.event_log",
                ["event_id", "event_type", "aggregate_id", "version", "actor", "payload", "trace_id", "created_at"],
                [[row[k] for k in ("event_id", "event_type", "aggregate_id", "version", "actor", "payload", "trace_id", "created_at")]],
            )
        except Exception:
            log.exception("failed to persist event %s", event.event_type)
            # durability is important but must not take down the run; the
            # in-memory mirror still has it for the dashboard
        finally:
            if span_ctx is not None:
                try:
                    span_ctx.__exit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass
