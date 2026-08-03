from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from zentra_domain_investigation import (
    InvestigationThread,
    ThreadMessage,
    ThreadMessageError,
    ThreadMessageKind,
    ThreadStatus,
    ThreadTransitionError,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def test_thread_requires_its_first_message_identity() -> None:
    thread = InvestigationThread.create(
        thread_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        initiating_message_id=uuid4(),
        title="Why did EU refunds increase?",
        now=NOW,
    )

    assert thread.status is ThreadStatus.DRAFT
    assert thread.archived_from_status is None


@pytest.mark.parametrize("content", ["", "   ", "x" * 4001, "bad\x00message"])
def test_message_rejects_empty_oversized_or_unsafe_text(content: str) -> None:
    with pytest.raises(ThreadMessageError):
        ThreadMessage.create(
            message_id=uuid4(),
            thread_id=uuid4(),
            tenant_id=uuid4(),
            author_id=uuid4(),
            kind=ThreadMessageKind.USER_QUESTION,
            content=content,
            now=NOW,
        )


def test_messages_are_immutable_values() -> None:
    message = ThreadMessage.create(
        message_id=uuid4(),
        thread_id=uuid4(),
        tenant_id=uuid4(),
        author_id=uuid4(),
        kind=ThreadMessageKind.USER_QUESTION,
        content="  Why did refunds increase?  ",
        now=NOW,
    )

    assert message.content == "Why did refunds increase?"
    with pytest.raises(AttributeError):
        message.content = "changed"  # type: ignore[misc]


def test_archive_and_restore_preserve_the_previous_thread_state() -> None:
    thread = InvestigationThread.create(
        thread_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        initiating_message_id=uuid4(),
        title="Refunds",
        now=NOW,
    )
    thread.activate(NOW)
    thread.archive(NOW)

    assert thread.status is ThreadStatus.ARCHIVED
    assert thread.archived_from_status is ThreadStatus.ACTIVE

    thread.restore(NOW)
    assert thread.status is ThreadStatus.ACTIVE
    assert thread.archived_from_status is None


def test_only_draft_threads_without_analytical_work_can_be_deleted() -> None:
    thread = InvestigationThread.create(
        thread_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        initiating_message_id=uuid4(),
        title="Refunds",
        now=NOW,
    )

    thread.ensure_deletable(has_analytical_work=False)
    with pytest.raises(ThreadTransitionError):
        thread.ensure_deletable(has_analytical_work=True)


def test_archived_threads_are_not_writable() -> None:
    thread = InvestigationThread.create(
        thread_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        initiating_message_id=uuid4(),
        title="Refunds",
        now=NOW,
    )
    thread.archive(NOW)

    with pytest.raises(ThreadTransitionError):
        thread.ensure_writable()
