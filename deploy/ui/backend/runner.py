"""Dedicated, restartable worker for queued LibreChat investigations.

The UI only enqueues uploads.  This process holds the synchronous LibreChat
chat-completion connection and records the agent's persisted handoff, so the
browser and the UI web server are never coupled to an instrumentation run.
"""

from __future__ import annotations

import asyncio

from .app import ensure_container, init_schema, queue_watcher


async def main() -> None:
    await asyncio.to_thread(ensure_container)
    # ClickHouse Cloud can briefly reject concurrent/just-finished ALTER
    # metadata propagation. The worker is the sole schema initializer, and a
    # bounded retry keeps that transient from taking the queue offline.
    for attempt in range(6):
        try:
            await asyncio.to_thread(init_schema)
            break
        except Exception:
            if attempt == 5:
                raise
            await asyncio.sleep(2 ** attempt)
    await queue_watcher()


if __name__ == "__main__":
    asyncio.run(main())
