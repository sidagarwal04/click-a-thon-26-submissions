from __future__ import annotations


class ProviderError(RuntimeError):
    """Base for every failure a provider rung can produce."""


class ProviderUnavailableError(ProviderError):
    """Rate limited, overloaded, timed out, or unreachable.

    The next rung should be tried: the request itself was fine.
    """


class ProviderAuthError(ProviderError):
    """Rejected our credentials.

    Never falls through. A bad or missing key is a configuration mistake, and
    silently spending money on the next provider would hide it.
    """


class ProviderTruncatedError(ProviderError):
    """The response hit the token ceiling before it finished.

    Gemini Flash has a documented failure where constrained decoding enters a
    repetition loop inside a JSON number literal and runs to the ceiling, so a
    truncated response is unusable rather than merely short.
    """


class ChainExhaustedError(ProviderError):
    """Every rung failed.

    Carries what each one did, so the ledger records why an investigation could
    not run rather than just that it didn't.
    """

    def __init__(self, role: str, attempts: list[str]) -> None:
        self.role = role
        self.attempts = attempts
        detail = "; ".join(attempts) if attempts else "no providers configured"
        super().__init__(f"All model providers failed for {role}: {detail}")
