from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from zentra_adapter_postgres import IdentityContext
from zentra_application_investigation import (
    RoutingDisposition,
    RoutingResult,
    ThreadConflictError,
    ThreadDetail,
    ThreadMessageDetail,
    ThreadPage,
    ThreadSummary,
)
from zentra_domain_investigation import ThreadMessageKind, ThreadStatus

from zentra_api.thread_schemas import ThreadResponse

from .test_api import client

AUTH = {"Authorization": "Bearer valid"}
NOW = datetime(2026, 8, 1, tzinfo=UTC)
PROJECT_ID = UUID("42000000-0000-0000-0000-000000000001")
THREAD_ID = UUID("43000000-0000-0000-0000-000000000001")
MESSAGE_ID = UUID("44000000-0000-0000-0000-000000000001")


def routing() -> RoutingResult:
    return RoutingResult(
        disposition=RoutingDisposition.UNSUPPORTED,
        scenario_key=None,
        canonical_question=None,
        clarification="Please choose a supported question.",
        suggestions=("Why did EU refunds increase from June to July 2026?",),
    )


def detail(*, status: ThreadStatus = ThreadStatus.DRAFT) -> ThreadDetail:
    return ThreadDetail(
        thread_id=THREAD_ID,
        project_id=PROJECT_ID,
        title="How is the business doing?",
        status=status,
        created_at=NOW,
        updated_at=NOW,
        latest_activity_at=NOW,
        messages=(
            ThreadMessageDetail(
                message_id=MESSAGE_ID,
                kind=ThreadMessageKind.USER_QUESTION,
                content="How is the business doing?",
                created_at=NOW,
                authored_by_user=True,
            ),
        ),
        investigation_id=None,
        routing=routing(),
        can_append_message=status is ThreadStatus.DRAFT,
        can_archive=status is not ThreadStatus.ARCHIVED,
        can_restore=status is ThreadStatus.ARCHIVED,
        can_delete=status is ThreadStatus.DRAFT,
    )


class ThreadStub:
    def __init__(self) -> None:
        self.deleted = False
        self.last_content: str | None = None

    async def create(
        self, *args: object, content: str, **kwargs: object
    ) -> ThreadDetail:
        self.last_content = content
        return detail()

    async def list(self, *args: object, **kwargs: object) -> ThreadPage:
        return ThreadPage(
            items=(
                ThreadSummary(
                    thread_id=THREAD_ID,
                    project_id=PROJECT_ID,
                    title="How is the business doing?",
                    status=ThreadStatus.DRAFT,
                    latest_activity_at=NOW,
                    investigation_id=None,
                ),
            ),
            next_cursor="next",
        )

    async def get(self, *args: object, **kwargs: object) -> ThreadDetail:
        return detail()

    async def append(
        self, *args: object, content: str, **kwargs: object
    ) -> ThreadDetail:
        self.last_content = content
        return detail()

    async def archive(self, *args: object, **kwargs: object) -> ThreadDetail:
        return detail(status=ThreadStatus.ARCHIVED)

    async def restore(self, *args: object, **kwargs: object) -> ThreadDetail:
        return detail()

    async def delete(self, *args: object, **kwargs: object) -> None:
        self.deleted = True


def bind_identity(monkeypatch, *, role: str = "member") -> None:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="member@example.com",
            tenant_name="Acme",
            role=role,
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)


def test_thread_lifecycle_contracts_are_backend_owned(monkeypatch) -> None:
    bind_identity(monkeypatch)
    threads = ThreadStub()

    with client(threads=threads) as test_client:
        created = test_client.post(
            f"/v1/projects/{PROJECT_ID}/threads",
            headers=AUTH,
            json={"message": "How is the business doing?"},
        )
        listed = test_client.get(f"/v1/projects/{PROJECT_ID}/threads", headers=AUTH)
        fetched = test_client.get(f"/v1/threads/{THREAD_ID}", headers=AUTH)
        appended = test_client.post(
            f"/v1/threads/{THREAD_ID}/messages",
            headers=AUTH,
            json={"message": "EU refunds from June to July"},
        )
        archived = test_client.post(f"/v1/threads/{THREAD_ID}/archive", headers=AUTH)
        restored = test_client.post(f"/v1/threads/{THREAD_ID}/restore", headers=AUTH)
        deleted = test_client.delete(f"/v1/threads/{THREAD_ID}", headers=AUTH)

    assert created.status_code == 201
    assert created.json()["routing"]["disposition"] == "unsupported"
    assert created.json()["actions"]["can_delete"] is True
    assert listed.json()["next_cursor"] == "next"
    assert fetched.json()["thread_id"] == str(THREAD_ID)
    assert appended.status_code == 200
    assert archived.json()["status"] == "archived"
    assert restored.json()["status"] == "draft"
    assert deleted.status_code == 204
    assert threads.deleted is True


def test_thread_requests_forbid_extra_fields(monkeypatch) -> None:
    bind_identity(monkeypatch)

    with client(threads=ThreadStub()) as test_client:
        response = test_client.post(
            f"/v1/projects/{PROJECT_ID}/threads",
            headers=AUTH,
            json={"message": "Question", "scenario_key": "eu_refund_spike"},
        )

    assert response.status_code == 422


def test_thread_conflicts_have_stable_codes(monkeypatch) -> None:
    bind_identity(monkeypatch)

    class RefusingThreads(ThreadStub):
        async def append(
            self, *args: object, content: str, **kwargs: object
        ) -> ThreadDetail:
            raise ThreadConflictError("Thread is active")

    with client(threads=RefusingThreads()) as test_client:
        response = test_client.post(
            f"/v1/threads/{THREAD_ID}/messages",
            headers=AUTH,
            json={"message": "Another question"},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "thread_conflict"


def test_openapi_exposes_thread_operations() -> None:
    with client(threads=ThreadStub()) as test_client:
        openapi = test_client.get("/openapi.json").json()
        paths = openapi["paths"]

    assert {
        "/v1/projects/{project_id}/threads",
        "/v1/threads/{thread_id}",
        "/v1/threads/{thread_id}/messages",
        "/v1/threads/{thread_id}/archive",
        "/v1/threads/{thread_id}/restore",
    } <= set(paths)
    assert "delete" in paths["/v1/threads/{thread_id}"]
    example = openapi["components"]["schemas"]["ThreadResponse"]["examples"][0]
    assert ThreadResponse.model_validate(example).messages[1].kind == (
        ThreadMessageKind.ROUTER_CLARIFICATION.value
    )
