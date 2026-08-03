"""Process-local TTL cache for analytics dimension member lists only."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Optional

from conversation_agent import config

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cache_key(namespace: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(f"{namespace}:{blob}".encode()).hexdigest()
    return digest


def get(key: str) -> Optional[Any]:
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _store.pop(key, None)
            return None
        return value


def set(key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None:
    ttl = (
        float(ttl_seconds)
        if ttl_seconds is not None
        else float(getattr(config, "ANALYTICS_CACHE_TTL_SECONDS", 300))
    )
    expires_at = time.monotonic() + max(1.0, ttl)
    with _lock:
        _store[key] = (expires_at, value)
        # Soft bound to avoid unbounded growth in long-lived processes
        if len(_store) > 512:
            _evict_expired_unlocked(time.monotonic())


def clear() -> None:
    with _lock:
        _store.clear()


def _evict_expired_unlocked(now: float) -> None:
    dead = [k for k, (exp, _) in _store.items() if exp <= now]
    for k in dead:
        _store.pop(k, None)
