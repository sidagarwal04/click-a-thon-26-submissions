"""Background live monitor: polls fact_events' row count every
settings.live_poll_seconds, and the moment ingestion has been quiet for
settings.live_idle_seconds with nothing new, triggers exactly one
incremental scan+investigate pass (rca.incremental.run_incremental_pipeline).

There is no other trigger. No "batch done" signal, no per-day closure rule,
no periodic full rescan -- silence for the idle window is the entire
detection mechanism. Every state change is pushed to subscribed SSE clients
(see web.py's /api/live/events) so the dashboard reflects ingest/pipeline
activity without polling or a manual "Scan" click.
"""

import asyncio
import time
from dataclasses import dataclass, field

from . import incremental
from .config import settings
from .db import get_client


@dataclass
class LiveMonitor:
    poll_seconds: float = field(default_factory=lambda: settings.live_poll_seconds)
    idle_seconds: float = field(default_factory=lambda: settings.live_idle_seconds)
    _subscribers: list = field(default_factory=list)
    _last_row_count: int | None = field(default=None, repr=False)
    _last_change_time: float = field(default_factory=time.monotonic, repr=False)
    _last_pipeline_row_count: int | None = field(default=None, repr=False)
    _task: "asyncio.Task | None" = field(default=None, repr=False)
    _status: dict = field(default_factory=lambda: {"type": "starting"}, repr=False)

    def subscribe(self) -> "asyncio.Queue":
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        q.put_nowait(self._status)  # replay current state so a newly-opened tab isn't blank
        return q

    def unsubscribe(self, q) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _broadcast(self, event: dict) -> None:
        self._status = event
        for q in list(self._subscribers):
            q.put_nowait(event)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception as e:
                # A transient ClickHouse hiccup (or fact_events not existing
                # yet, before the first load_data.sh run) shouldn't kill the
                # poll loop permanently -- report it and keep polling.
                self._broadcast({"type": "error", "message": str(e)})
            await asyncio.sleep(self.poll_seconds)

    async def _tick(self) -> None:
        loop = asyncio.get_running_loop()
        row_count = await loop.run_in_executor(None, _fetch_row_count)
        now = time.monotonic()

        if row_count == 0:
            # A momentarily-empty fact_events (e.g. load_data.sh's DROP+
            # CREATE, caught mid-DDL before its own INSERT finishes) is not
            # "idle at zero rows" -- there's nothing to scan either way, so
            # just wait rather than let a transient 0 start (and then win)
            # the idle clock and fire a pipeline run against an empty table.
            self._last_row_count = None
            self._broadcast({"type": "waiting", "row_count": 0})
            return

        if row_count != self._last_row_count:
            self._last_row_count = row_count
            self._last_change_time = now
            self._broadcast({"type": "ingest", "row_count": row_count})
            return

        idle_seconds = now - self._last_change_time
        if idle_seconds < self.idle_seconds:
            self._broadcast({"type": "idle", "row_count": row_count, "idle_seconds": round(idle_seconds, 1)})
            return

        if self._last_pipeline_row_count == row_count:
            self._broadcast({"type": "settled", "row_count": row_count})
            return  # already ran for this exact count -- nothing new to do

        self._broadcast({"type": "pipeline_start", "row_count": row_count})
        summary = await loop.run_in_executor(None, incremental.run_incremental_pipeline)
        self._last_pipeline_row_count = row_count
        self._broadcast({
            "type": "pipeline_complete",
            "row_count": row_count,
            "reset": summary["reset"],
            "synced_rows": summary["synced_rows"],
            "investigation_ids": summary["investigation_ids"],
        })


def _fetch_row_count() -> int:
    # ad_events_raw, not fact_events -- fact_events is the *derived* table,
    # only updated by the sync step this same idle trigger decides to run.
    # Watching it for "has data landed" would be circular: it never changes
    # until we already decided to act on it. ad_events_raw is where
    # ingestion actually happens, so it's the real idle signal.
    client = get_client()
    row = client.query("SELECT count() FROM ad_events_raw").result_rows
    return int(row[0][0]) if row else 0


monitor = LiveMonitor()
