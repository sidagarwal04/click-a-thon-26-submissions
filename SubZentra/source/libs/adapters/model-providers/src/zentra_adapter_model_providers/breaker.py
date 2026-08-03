from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .providers import Provider

WINDOW = 5
FAILURE_THRESHOLD = 3
COOLDOWN = timedelta(seconds=60)


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class _ProviderState:
    outcomes: deque[bool] = field(default_factory=lambda: deque(maxlen=WINDOW))
    opened_at: datetime | None = None
    probing: bool = False


class ProviderCircuitBreaker:
    """Three-state breaker per provider (final architecture §3.7).

    Scoped to the provider rather than the tenant, because the limit being
    tripped is our own API key's rate limit — shared across every tenant in the
    process. Cerebras at 5 requests/minute will trip this constantly, which is
    the point: without it, every call pays the 429 round trip before falling
    through.
    """

    def __init__(self, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._now = now
        self._states: dict[Provider, _ProviderState] = {}

    def state(self, provider: Provider) -> BreakerState:
        entry = self._states.get(provider)
        if entry is None or entry.opened_at is None:
            return BreakerState.CLOSED
        if self._now() - entry.opened_at >= COOLDOWN:
            return BreakerState.HALF_OPEN
        return BreakerState.OPEN

    def allow(self, provider: Provider) -> bool:
        """Whether to attempt this provider now.

        Half-open lets exactly one probe through; further calls wait for its
        result rather than stampeding a provider that may still be down.
        """
        current = self.state(provider)
        if current is BreakerState.CLOSED:
            return True
        if current is BreakerState.OPEN:
            return False
        entry = self._states[provider]
        if entry.probing:
            return False
        entry.probing = True
        return True

    def record_success(self, provider: Provider) -> None:
        entry = self._states.setdefault(provider, _ProviderState())
        entry.outcomes.append(True)
        entry.opened_at = None
        entry.probing = False

    def record_failure(self, provider: Provider) -> None:
        entry = self._states.setdefault(provider, _ProviderState())
        entry.outcomes.append(False)
        entry.probing = False
        if entry.opened_at is not None:
            # A failed probe re-opens for a fresh cooldown.
            entry.opened_at = self._now()
            return
        if entry.outcomes.count(False) >= FAILURE_THRESHOLD:
            entry.opened_at = self._now()
            entry.outcomes.clear()
