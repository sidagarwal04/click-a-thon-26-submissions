"""Langfuse tracing wrapper.

Owner: platform. This is the ONLY module that imports langfuse. Everything else
uses span()/generation()/trace_run() so that Langfuse SDK churn stays contained.

The contract that matters for judging: every LLM call records the context layer
version it consumed, via the `context_version` argument. That is the evidence for
the "context freshness" criterion -- without it the claim is unfalsifiable.

If Langfuse credentials are absent the wrappers degrade to no-ops so the pipeline
still runs offline; `tracing_enabled()` reports which mode is active.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from dotenv import load_dotenv

load_dotenv()

#: A real Langfuse key is `pk-lf-<uuid>` / `sk-lf-<uuid>` -- the prefix plus a
#: substantial random tail. Anything at or below this length is a placeholder.
_KEY_PREFIXES = ("pk-lf-", "sk-lf-")
_MIN_REAL_KEY_LEN = 20


def _real(value: str | None) -> bool:
    """A placeholder key is worse than no key: it flips tracing 'on', every span export
    401s, and we still write a trace_url pointing at nothing -- which quietly breaks the
    "no trace, no credit" claim for anyone who cloned and ran `make setup`.

    The previous check tried to spot the `.env.example` stubs by stripping trailing dots
    and matching a suffix, but `"pk-lf-...".rstrip(".")` is `"pk-lf-"`, which does NOT
    end with `"pk-lf"` (the dash), so every stub was treated as a REAL key. Verified: it
    returned True for `pk-lf-...`, `sk-lf-...`, `pk-lf-` and `sk-lf-`.

    Judge on length instead of trying to enumerate placeholder shapes: a genuine key
    carries a long random tail, and no plausible stub does.
    """
    v = (value or "").strip()
    if not v or v.endswith("..."):
        return False
    if v.startswith(_KEY_PREFIXES):
        return len(v) >= _MIN_REAL_KEY_LEN
    # Not a recognisable Langfuse key shape at all; only treat it as real if it is
    # long enough to plausibly be a credential rather than a leftover placeholder.
    return len(v) >= _MIN_REAL_KEY_LEN


_ENABLED = _real(os.getenv("LANGFUSE_PUBLIC_KEY")) and _real(os.getenv("LANGFUSE_SECRET_KEY"))
_client: Any = None

# Region matters: a US-region project 401s against the default EU host. Accept
# either env var name -- the SDK only reads LANGFUSE_HOST, but LANGFUSE_BASE_URL
# is the name shown in parts of Langfuse's own docs, so honour both.
HOST = (
    os.getenv("LANGFUSE_HOST")
    or os.getenv("LANGFUSE_BASE_URL")
    or "https://cloud.langfuse.com"
).rstrip("/")
os.environ["LANGFUSE_HOST"] = HOST


def tracing_enabled() -> bool:
    return _ENABLED


def init_tracing() -> None:
    global _client
    if not _ENABLED or _client is not None:
        return
    from langfuse import get_client

    _client = get_client()


def new_run_id() -> str:
    return uuid.uuid4().hex


class _NullSpan:
    def update(self, **kwargs: Any) -> None:  # noqa: D102
        return None


@contextmanager
def trace_run(spec: str, run_id: str, context_version: int) -> Iterator[Any]:
    """Root of one pipeline run. All spans nest under this."""
    init_tracing()
    if not _ENABLED:
        yield _NullSpan()
        return
    from langfuse import propagate_attributes

    with _client.start_as_current_observation(
        as_type="span", name=f"pipeline_run:{spec}"
    ) as root:
        with propagate_attributes(
            trace_name=f"pipeline_run:{spec}",
            metadata={
                "feature_slug": spec,
                "run_id": run_id,
                "context_version": context_version,
            },
            tags=["atlys", "pipeline"],
        ):
            yield root


@contextmanager
def span(name: str, **meta: Any) -> Iterator[Any]:
    init_tracing()
    if not _ENABLED:
        yield _NullSpan()
        return
    with _client.start_as_current_observation(as_type="span", name=name) as sp:
        if meta:
            sp.update(metadata=meta)
        yield sp


@contextmanager
def generation(name: str, model: str, context_version: int, **meta: Any) -> Iterator[Any]:
    """An LLM call. `context_version` is mandatory -- it is the freshness evidence."""
    init_tracing()
    if not _ENABLED:
        yield _NullSpan()
        return
    with _client.start_as_current_observation(as_type="generation", name=name) as gen:
        gen.update(model=model, metadata={"context_version": context_version, **meta})
        yield gen


def current_trace_id() -> str:
    init_tracing()
    if not _ENABLED:
        return ""
    return _client.get_current_trace_id() or ""


_PROJECT_ID: str | None = None


def project_id() -> str:
    """The Langfuse project id, needed for a linkable trace URL.

    Resolved once from the API and cached for the process. `LANGFUSE_PROJECT_ID`
    overrides it so an offline/air-gapped run can still emit correct links.
    """
    global _PROJECT_ID
    if _PROJECT_ID is not None:
        return _PROJECT_ID
    _PROJECT_ID = os.getenv("LANGFUSE_PROJECT_ID", "").strip()
    if not _PROJECT_ID and _ENABLED:
        try:
            init_tracing()
            projects = _client.api.projects.get()
            data = getattr(projects, "data", None) or []
            if data:
                _PROJECT_ID = str(getattr(data[0], "id", "") or "")
        except Exception:  # noqa: BLE001 - a link is never worth failing a run over
            _PROJECT_ID = ""
    return _PROJECT_ID


def trace_url_for(trace_id: str) -> str:
    """A URL that actually opens the trace.

    Langfuse's console route is `/project/<project_id>/traces/<trace_id>`; the shorter
    `/trace/<trace_id>` this used to emit is NOT a valid route and 404s, which quietly
    broke every "no trace, no credit" link we wrote into artifacts and pipeline_runs.
    Falls back to the host root when the project id cannot be resolved -- a landing page
    the reader can search from beats a link that looks right and dead-ends.
    """
    if not trace_id:
        return ""
    pid = project_id()
    if pid:
        return f"{HOST}/project/{pid}/traces/{trace_id}"
    return HOST


def current_trace_url() -> str:
    return trace_url_for(current_trace_id())


def verify() -> tuple[bool, str]:
    """Prove credentials actually work. 'No trace, no credit' -- never assume."""
    init_tracing()
    if not _ENABLED:
        return False, "disabled: no Langfuse keys in the environment"
    try:
        ok = _client.auth_check()
    except Exception as exc:  # noqa: BLE001
        return False, f"auth_check raised against {HOST}: {exc}"
    return bool(ok), (f"authenticated against {HOST}" if ok else f"REJECTED by {HOST}")


def flush() -> None:
    if _ENABLED and _client is not None:
        _client.flush()
