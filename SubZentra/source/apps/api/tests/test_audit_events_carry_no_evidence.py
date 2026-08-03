"""The ledger is metadata, including when something goes wrong.

ADR 0006 makes the audit ledger metadata-only, and #23 asks for a regression
test that rejects raw rows, prompts, Finding narrative, aggregate values,
credentials and hidden reasoning in *audit events and errors* — not only in
traces.

Errors are the interesting half. Every other field on an Audit Entry has a
shape that cannot hold prose: a UUID, a token count, a cost, a status from a
closed set. `errors` is a tuple of free strings, and the graph formats them as
`f"{type(error).__name__}: {error}"`, so an Insight refusal that names a claim
position and the governed metric it could not ground would travel into
ClickHouse verbatim and stay there — the ledger is immutable, so a leak here is
permanent and survives the evidence deletion that was supposed to erase it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from zentra_api.audit_delivery import AuditDeliveryCoordinator, error_categories

_entry = AuditDeliveryCoordinator._entry

_POISON = (
    "UngroundedClaimError: claim 2 says checkout conversion fell to 0.1743 in "
    "EMEA, but no validated aggregate supports it",
    "MalformedAgentResponseError: <thinking>the analyst is probably wrong "
    "about region</thinking>",
    "ProviderError: 401 from api.anthropic.com with key sk-ant-api03-abcdef",
)


class _Record:
    """The fields `_entry` reads, and no more."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.created_at = datetime.now(UTC)
        self.event_id = uuid4()
        self.tenant_id = uuid4()
        self.investigation_id = uuid4()


def _payload(errors: tuple[str, ...]) -> dict:
    return {
        "entry_id": str(uuid4()),
        "trace_id": str(uuid4()),
        "span_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "investigation_id": str(uuid4()),
        "event_type": "agent.execution_failed",
        "occurred_at": datetime.now(UTC).isoformat(),
        "input_hash": "sha256:abc",
        "status": "running",
        "metadata": {
            "agent_id": "insight_v1",
            "latency_ms": 12,
            "errors": list(errors),
        },
    }


def test_an_error_message_never_reaches_the_ledger() -> None:
    """The type survives; everything after the colon does not."""
    entry = _entry(_Record(_payload(_POISON)))

    written = " ".join(entry.errors)
    for fragment in ("0.1743", "EMEA", "<thinking>", "sk-ant-api03", "checkout"):
        assert fragment not in written


def test_the_error_type_does_survive() -> None:
    """Stripping the message must not strip the diagnosis.

    An entry that recorded nothing would pass the test above and leave an
    operator unable to tell a grounding refusal from a provider outage.
    """
    entry = _entry(_Record(_payload(_POISON)))

    assert "UngroundedClaimError" in entry.errors
    assert "MalformedAgentResponseError" in entry.errors


def test_an_unrecognized_error_is_named_as_unrecognized() -> None:
    """`ProviderError` is not on the allowlist, so it reports as unexpected.

    Reporting the raw prefix instead would publish whatever preceded the first
    colon of a string this code does not control.
    """
    entry = _entry(_Record(_payload(_POISON)))

    assert "unexpected" in entry.errors
    assert not any("401" in error for error in entry.errors)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("UngroundedClaimError: anything at all", "UngroundedClaimError"),
        ("AbsentEvidenceError", "AbsentEvidenceError"),
        ("0.1743: the metric fell", "unexpected"),
        ("no colon here", "unexpected"),
        ("", "unexpected"),
    ],
)
def test_categorisation_is_an_allowlist_not_a_split(raw: str, expected: str) -> None:
    assert error_categories((raw,)) == (expected,)


def test_no_errors_stays_no_errors() -> None:
    """An absent error and an unexpected one are different claims."""
    assert error_categories(()) == ()
