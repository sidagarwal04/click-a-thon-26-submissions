import hashlib
import time


def sha256_hex(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class TTLCache:
    """Minimal in-memory seen-key cache. ponytail: one process only, global dict —
    move to a shared store (ClickHouse/redis) if this ever runs behind more than one
    worker."""

    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._seen: dict[str, float] = {}

    def seen(self, key: str) -> bool:
        now = time.monotonic()
        self._evict_stale(now)
        if key in self._seen:
            return True
        self._seen[key] = now
        return False

    def _evict_stale(self, now: float) -> None:
        stale = [k for k, ts in self._seen.items() if now - ts > self._ttl]
        for k in stale:
            del self._seen[k]


def iter_leaves(obj):
    """Recursively yield every non-container leaf value in a nested dict/list structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from iter_leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_leaves(v)
    else:
        yield obj


def content_to_text(content) -> str:
    """Normalizes a LangChain message .content value to plain text — most chat models
    return a str, but some (Gemini included) can return a list of content-block parts."""
    if isinstance(content, str):
        return content
    return "".join(
        part if isinstance(part, str) else part.get("text", "") for part in content
    )
