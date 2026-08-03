"""In-process keyed locks for approve / DDL serialization (hackathon MVP).

uvicorn must run with a single worker — these locks are per-process only.
Acquire multiple keys in sorted order to avoid deadlocks (run_id + table).
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class KeyedLocks:
    """Lazy lock registry: one `threading.Lock` per string key."""

    def __init__(self) -> None:
        self._meta = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def _lock_for(self, key: str) -> threading.Lock:
        with self._meta:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    @contextmanager
    def acquire(self, *keys: str, timeout: float | None = 120.0) -> Iterator[None]:
        """Acquire one or more locks; keys are sorted to prevent deadlock."""
        ordered = sorted({k for k in keys if k})
        held: list[threading.Lock] = []
        try:
            for key in ordered:
                lock = self._lock_for(key)
                if timeout is None:
                    lock.acquire()
                elif not lock.acquire(timeout=timeout):
                    raise TimeoutError(f"timed out acquiring lock {key!r}")
                held.append(lock)
            yield
        finally:
            for lock in reversed(held):
                lock.release()


# Process-wide locks shared by InstrumentationAgent instances
pipeline_locks = KeyedLocks()
