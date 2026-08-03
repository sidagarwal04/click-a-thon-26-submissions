from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from zentra_domain_investigation import (
    MessageEventPayload,
    ThreadEvent,
    WorkFeedEventKind,
)

from zentra_api.thread_routes import stream_thread_events

THREAD_ID = UUID("10000000-0000-0000-0000-000000000001")


class Threads:
    def __init__(self, events: tuple[ThreadEvent, ...]) -> None:
        self.values = events
        self.after: list[int] = []

    async def event_cursor(self, *_: object) -> int:
        return self.values[-1].sequence if self.values else 0

    async def events(
        self, *_: object, after: int, **__: object
    ) -> tuple[ThreadEvent, ...]:
        self.after.append(after)
        return tuple(value for value in self.values if value.sequence > after)


class Request:
    def __init__(self, threads: Threads, *, last_event_id: str = "0") -> None:
        self.headers = {"last-event-id": last_event_id}
        self.app = SimpleNamespace(
            state=SimpleNamespace(dependencies=SimpleNamespace(threads=threads))
        )
        self.checks = 0

    async def is_disconnected(self) -> bool:
        self.checks += 1
        return self.checks > 1


def _event(sequence: int) -> ThreadEvent:
    return ThreadEvent(
        event_id=UUID(int=sequence),
        tenant_id=UUID("20000000-0000-0000-0000-000000000001"),
        thread_id=THREAD_ID,
        sequence=sequence,
        kind=WorkFeedEventKind.MESSAGE_ADDED,
        occurred_at=datetime(2026, 8, 1, tzinfo=UTC),
        payload=MessageEventPayload(
            message_id=UUID("30000000-0000-0000-0000-000000000001"),
            message_kind="user_question",
        ),
    )


@pytest.mark.asyncio
async def test_sse_resumes_after_last_event_id_and_emits_decimal_sequence() -> None:
    threads = Threads((_event(4), _event(5)))
    request = Request(threads, last_event_id="4")
    response = await stream_thread_events(
        THREAD_ID,
        request,  # type: ignore[arg-type]
        SimpleNamespace(actor=object()),  # type: ignore[arg-type]
        after=None,
    )

    chunks = [chunk async for chunk in response.body_iterator]

    assert threads.after == [4]
    assert chunks[0].startswith("id: 5\nevent: thread.message_added\n")
    assert '"sequence":5' in chunks[0]
