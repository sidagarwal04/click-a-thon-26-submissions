from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from zentra_domain_investigation import (
    TERMINAL_STATUSES,
    ExecutionJob,
    Investigation,
    InvestigationEventPayload,
    InvestigationStatus,
    InvestigationThread,
    MessageEventPayload,
    RoutingEventPayload,
    ThreadEvent,
    ThreadMessage,
    ThreadMessageKind,
    ThreadStatus,
    ThreadTransitionError,
    WorkFeedEventKind,
)

from .dto import (
    AuditDelivery,
    AuthenticatedActor,
    PermissionDeniedError,
    Role,
    UsageSummary,
)
from .thread_dto import (
    RoutingDisposition,
    RoutingResult,
    ThreadConflictError,
    ThreadCursor,
    ThreadDetail,
    ThreadInvestigationSummary,
    ThreadNotFoundError,
    ThreadPage,
)
from .thread_ports import IntakePort, ThreadUnitOfWork, ThreadUnitOfWorkFactory
from .thread_routing import deterministic_thread_title
from .thread_snapshot import build_thread_detail, require_project, validate_page_size

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
THREAD_MUTATOR_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.MEMBER})

_ROUTABLE_KINDS = frozenset(
    {ThreadMessageKind.USER_QUESTION, ThreadMessageKind.USER_CLARIFICATION}
)


def _combined_question_text(messages: tuple[ThreadMessage, ...]) -> str:
    """A Draft Thread's user and clarification messages, as one question.

    Intake reasons over text, not tokens, so accumulating a Draft Thread's
    messages into one passage (rather than merging separately-matched token
    sets, as the keyword router did) is what lets a later clarification like
    "In Europe" resolve a question the first message alone could not.
    """
    return "\n".join(
        message.content for message in messages if message.kind in _ROUTABLE_KINDS
    )


class ThreadService:
    def __init__(
        self,
        *,
        unit_of_work_factory: ThreadUnitOfWorkFactory,
        intake: IntakePort,
        now: Callable[[], datetime],
        new_id: Callable[[], UUID],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._intake = intake
        self._now = now
        self._new_id = new_id

    async def create(
        self,
        actor: AuthenticatedActor,
        *,
        project_id: UUID,
        content: str,
        data_connection_id: UUID | None = None,
    ) -> ThreadDetail:
        self._require_mutator(actor)
        now = self._now()
        thread_id = self._new_id()
        message_id = self._new_id()
        message = ThreadMessage.create(
            message_id=message_id,
            thread_id=thread_id,
            tenant_id=actor.tenant_id,
            author_id=actor.user_id,
            kind=ThreadMessageKind.USER_QUESTION,
            content=content,
            now=now,
        )
        routing = await self._intake.resolve(
            message.content,
            tenant_id=actor.tenant_id,
            data_connection_id=data_connection_id,
        )
        title_source = routing.canonical_question or message.content
        thread = InvestigationThread.create(
            thread_id=thread_id,
            tenant_id=actor.tenant_id,
            project_id=project_id,
            initiating_message_id=message_id,
            title=deterministic_thread_title(title_source),
            now=now,
        )
        async with self._uow(actor) as unit_of_work:
            await self._require_writable_project(unit_of_work, project_id)
            await unit_of_work.threads.add_thread(thread)
            await unit_of_work.threads.add_message(message)
            await unit_of_work.work_feed.append(
                tenant_id=actor.tenant_id,
                thread_id=thread_id,
                kind=WorkFeedEventKind.MESSAGE_ADDED,
                payload=MessageEventPayload(
                    message_id=message.message_id,
                    message_kind=message.kind.value,
                ),
                occurred_at=now,
                event_id=self._new_id(),
            )
            investigation_id, router_messages = await self._apply_routing(
                unit_of_work,
                actor,
                thread,
                message,
                routing,
                now,
                data_connection_id=data_connection_id,
            )
            await unit_of_work.organization.record_project_activity(
                project_id, occurred_at=now
            )
            await unit_of_work.commit()
        return build_thread_detail(
            thread,
            (message,) + router_messages,
            investigation_id,
            routing,
            actor,
        )

    async def append(
        self,
        actor: AuthenticatedActor,
        *,
        thread_id: UUID,
        content: str,
        data_connection_id: UUID | None = None,
    ) -> ThreadDetail:
        self._require_mutator(actor)
        now = self._now()
        async with self._uow(actor) as unit_of_work:
            thread = self._require_thread(
                await unit_of_work.threads.get_thread(thread_id, for_update=True)
            )
            await self._require_writable_project(unit_of_work, thread.project_id)
            if thread.status is ThreadStatus.ARCHIVED:
                raise ThreadConflictError("Archived Threads cannot accept messages")
            if thread.status is ThreadStatus.ACTIVE:
                return await self._append_follow_up(
                    unit_of_work, actor, thread, content, now
                )
            message = ThreadMessage.create(
                message_id=self._new_id(),
                thread_id=thread_id,
                tenant_id=actor.tenant_id,
                author_id=actor.user_id,
                kind=ThreadMessageKind.USER_CLARIFICATION,
                content=content,
                now=now,
            )
            existing_messages = await unit_of_work.threads.messages_for_thread(
                thread_id
            )
            routing = await self._intake.resolve(
                _combined_question_text(existing_messages + (message,)),
                tenant_id=actor.tenant_id,
                data_connection_id=data_connection_id,
            )
            thread.record_message(now)
            await unit_of_work.threads.add_message(message)
            await unit_of_work.work_feed.append(
                tenant_id=actor.tenant_id,
                thread_id=thread_id,
                kind=WorkFeedEventKind.MESSAGE_ADDED,
                payload=MessageEventPayload(
                    message_id=message.message_id,
                    message_kind=message.kind.value,
                ),
                occurred_at=now,
                event_id=self._new_id(),
            )
            investigation_id, _ = await self._apply_routing(
                unit_of_work,
                actor,
                thread,
                message,
                routing,
                now,
                data_connection_id=data_connection_id,
            )
            await unit_of_work.threads.save_thread(thread)
            await unit_of_work.organization.record_project_activity(
                thread.project_id, occurred_at=now
            )
            await unit_of_work.commit()
            messages = await unit_of_work.threads.messages_for_thread(thread_id)
            return build_thread_detail(
                thread, messages, investigation_id, routing, actor
            )

    async def _append_follow_up(
        self,
        unit_of_work: ThreadUnitOfWork,
        actor: AuthenticatedActor,
        thread: InvestigationThread,
        content: str,
        now: datetime,
    ) -> ThreadDetail:
        latest = await unit_of_work.investigations.latest_for_thread(
            thread.thread_id, for_update=True
        )
        if latest is None or latest.status not in TERMINAL_STATUSES:
            raise ThreadConflictError(
                "The latest Investigation must finish before a follow-up"
            )
        message = ThreadMessage.create(
            message_id=self._new_id(),
            thread_id=thread.thread_id,
            tenant_id=actor.tenant_id,
            author_id=actor.user_id,
            kind=ThreadMessageKind.USER_QUESTION,
            content=content,
            now=now,
        )
        routing = await self._intake.resolve(
            message.content,
            tenant_id=actor.tenant_id,
            data_connection_id=latest.data_connection_id,
        )
        normalized = message.content.casefold()
        published_reference = any(
            token in normalized
            for token in ("again", "latest", "re-run", "rerun", "same")
        )
        if (
            routing.disposition is not RoutingDisposition.RESOLVED
            and published_reference
            and latest.status is InvestigationStatus.COMPLETED
        ):
            routing = RoutingResult(
                disposition=RoutingDisposition.RESOLVED,
                scenario_key=latest.scenario_key,
                canonical_question=latest.question,
                clarification=None,
                suggestions=(),
            )
        thread.record_message(now)
        await unit_of_work.threads.add_message(message)
        await unit_of_work.work_feed.append(
            tenant_id=actor.tenant_id,
            thread_id=thread.thread_id,
            kind=WorkFeedEventKind.MESSAGE_ADDED,
            payload=MessageEventPayload(
                message_id=message.message_id,
                message_kind=message.kind.value,
            ),
            occurred_at=now,
            event_id=self._new_id(),
        )
        investigation_id = latest.investigation_id
        if routing.disposition is RoutingDisposition.RESOLVED:
            assert routing.canonical_question is not None
            follow_up = Investigation.create(
                investigation_id=self._new_id(),
                tenant_id=actor.tenant_id,
                question=routing.canonical_question,
                now=now,
                data_connection_id=latest.data_connection_id,
                thread_id=thread.thread_id,
                thread_sequence=(latest.thread_sequence or 0) + 1,
                initiating_message_id=message.message_id,
                parent_investigation_id=latest.investigation_id,
            )
            follow_up.start(now)
            await unit_of_work.investigations.add(follow_up)
            await unit_of_work.jobs.add_job(
                ExecutionJob.create(
                    job_id=self._new_id(),
                    tenant_id=actor.tenant_id,
                    investigation_id=follow_up.investigation_id,
                    now=now,
                )
            )
            await unit_of_work.outbox.enqueue(follow_up.events)
            await unit_of_work.work_feed.append(
                tenant_id=actor.tenant_id,
                thread_id=thread.thread_id,
                kind=WorkFeedEventKind.INVESTIGATION_QUEUED,
                payload=InvestigationEventPayload(
                    investigation_id=follow_up.investigation_id,
                    status=follow_up.status,
                    parent_investigation_id=latest.investigation_id,
                ),
                occurred_at=now,
                event_id=self._new_id(),
            )
            investigation_id = follow_up.investigation_id
        else:
            router_message = self._router_messages(thread, routing, now)[0]
            await unit_of_work.threads.add_message(router_message)
            await unit_of_work.work_feed.append(
                tenant_id=actor.tenant_id,
                thread_id=thread.thread_id,
                kind=WorkFeedEventKind.ROUTING_CLARIFICATION,
                payload=RoutingEventPayload(
                    disposition=routing.disposition.value,
                    suggestion_count=len(routing.suggestions),
                ),
                occurred_at=now,
                event_id=self._new_id(),
            )
        await unit_of_work.threads.save_thread(thread)
        await unit_of_work.organization.record_project_activity(
            thread.project_id, occurred_at=now
        )
        await unit_of_work.commit()
        messages = await unit_of_work.threads.messages_for_thread(thread.thread_id)
        return build_thread_detail(thread, messages, investigation_id, routing, actor)

    async def get(self, actor: AuthenticatedActor, thread_id: UUID) -> ThreadDetail:
        async with self._uow(actor) as unit_of_work:
            thread = self._require_thread(
                await unit_of_work.threads.get_thread(thread_id)
            )
            messages = await unit_of_work.threads.messages_for_thread(thread_id)
            investigation_id = await unit_of_work.threads.investigation_id_for_thread(
                thread_id
            )
            investigations = await unit_of_work.investigations.all_for_thread(thread_id)
            event_cursor = await unit_of_work.work_feed.latest_sequence(thread_id)
            summaries: list[ThreadInvestigationSummary] = []
            for investigation in investigations:
                approval = await unit_of_work.approvals.get_for_investigation(
                    investigation.investigation_id
                )
                draft = await unit_of_work.draft_findings.latest_for_investigation(
                    investigation.investigation_id
                )
                citations = await unit_of_work.citations.for_investigation(
                    investigation.investigation_id
                )
                usage = await unit_of_work.agent_executions.usage_for_investigation(
                    investigation.investigation_id
                )
                audit = await unit_of_work.outbox.all_for_investigation(
                    investigation.investigation_id
                )
                summaries.append(
                    ThreadInvestigationSummary(
                        investigation_id=investigation.investigation_id,
                        sequence=investigation.thread_sequence or 0,
                        status=investigation.status,
                        parent_investigation_id=investigation.parent_investigation_id,
                        retry_of_investigation_id=(
                            investigation.retry_of_investigation_id
                        ),
                        created_at=investigation.created_at,
                        updated_at=investigation.updated_at,
                        question=investigation.question,
                        scenario_key=investigation.scenario_key,
                        version=investigation.version,
                        evaluation_attempts=investigation.evaluation_attempts,
                        finished_at=investigation.finished_at,
                        finding=investigation.finding,
                        draft_finding=draft,
                        outcome=investigation.outcome,
                        approval=approval,
                        citations=citations,
                        audit_delivery=(
                            AuditDelivery.PENDING
                            if any(record.dispatched_at is None for record in audit)
                            else AuditDelivery.COMPLETE
                        ),
                        usage=usage,
                        can_decide_approval=(
                            actor.role in {Role.OWNER, Role.ADMIN}
                            and approval is not None
                            and approval.status.value == "pending"
                        ),
                    )
                )
            aggregate_usage = UsageSummary(
                input_tokens=sum(value.usage.input_tokens for value in summaries),
                output_tokens=sum(value.usage.output_tokens for value in summaries),
                cost_usd=sum(
                    (value.usage.cost_usd for value in summaries),
                    start=UsageSummary().cost_usd,
                ),
                latency_ms=sum(value.usage.latency_ms for value in summaries),
            )
        return build_thread_detail(
            thread,
            messages,
            investigation_id,
            None,
            actor,
            investigations=investigations,
            investigation_summaries=tuple(summaries),
            event_cursor=event_cursor,
            usage=aggregate_usage,
        )

    async def events(
        self,
        actor: AuthenticatedActor,
        *,
        thread_id: UUID,
        after: int,
        limit: int = 500,
    ) -> tuple[ThreadEvent, ...]:
        if after < 0 or limit < 1 or limit > 500:
            raise ValueError("Work Feed cursor or limit is invalid")
        async with self._uow(actor) as unit_of_work:
            self._require_thread(await unit_of_work.threads.get_thread(thread_id))
            return await unit_of_work.work_feed.events_after(
                thread_id, after=after, limit=limit
            )

    async def event_cursor(self, actor: AuthenticatedActor, thread_id: UUID) -> int:
        async with self._uow(actor) as unit_of_work:
            self._require_thread(await unit_of_work.threads.get_thread(thread_id))
            return await unit_of_work.work_feed.latest_sequence(thread_id)

    async def list(
        self,
        actor: AuthenticatedActor,
        *,
        project_id: UUID,
        include_archived: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> ThreadPage:
        limit = validate_page_size(limit, MAX_PAGE_SIZE)
        after = ThreadCursor.decode(cursor) if cursor else None
        async with self._uow(actor) as unit_of_work:
            require_project(await unit_of_work.organization.get_project(project_id))
            page = await unit_of_work.threads.list_threads(
                project_id=project_id,
                include_archived=include_archived,
                limit=limit,
                after=after,
            )
        return ThreadPage(
            items=page.items,
            next_cursor=page.next_cursor.encode() if page.next_cursor else None,
        )

    async def archive(self, actor: AuthenticatedActor, thread_id: UUID) -> ThreadDetail:
        self._require_mutator(actor)
        return await self._change_status(actor, thread_id, restore=False)

    async def restore(self, actor: AuthenticatedActor, thread_id: UUID) -> ThreadDetail:
        self._require_mutator(actor)
        return await self._change_status(actor, thread_id, restore=True)

    async def delete(self, actor: AuthenticatedActor, thread_id: UUID) -> None:
        self._require_mutator(actor)
        async with self._uow(actor) as unit_of_work:
            thread = self._require_thread(
                await unit_of_work.threads.get_thread(thread_id, for_update=True)
            )
            investigation_id = await unit_of_work.threads.investigation_id_for_thread(
                thread_id
            )
            try:
                thread.ensure_deletable(
                    has_analytical_work=investigation_id is not None
                )
            except ThreadTransitionError as error:
                raise ThreadConflictError(str(error)) from error
            await unit_of_work.threads.delete_thread(thread_id)
            await unit_of_work.commit()

    async def _change_status(
        self, actor: AuthenticatedActor, thread_id: UUID, *, restore: bool
    ) -> ThreadDetail:
        now = self._now()
        async with self._uow(actor) as unit_of_work:
            thread = self._require_thread(
                await unit_of_work.threads.get_thread(thread_id, for_update=True)
            )
            if restore:
                await self._require_writable_project(unit_of_work, thread.project_id)
                thread.restore(now)
            else:
                thread.archive(now)
            await unit_of_work.threads.save_thread(thread)
            await unit_of_work.commit()
            messages = await unit_of_work.threads.messages_for_thread(thread_id)
            investigation_id = await unit_of_work.threads.investigation_id_for_thread(
                thread_id
            )
        return build_thread_detail(thread, messages, investigation_id, None, actor)

    async def _apply_routing(
        self,
        unit_of_work: ThreadUnitOfWork,
        actor: AuthenticatedActor,
        thread: InvestigationThread,
        message: ThreadMessage,
        routing: RoutingResult,
        now: datetime,
        data_connection_id: UUID | None = None,
    ) -> tuple[UUID | None, tuple[ThreadMessage, ...]]:
        if routing.disposition is not RoutingDisposition.RESOLVED:
            router_messages = self._router_messages(thread, routing, now)
            await unit_of_work.threads.add_message(router_messages[0])
            await unit_of_work.work_feed.append(
                tenant_id=actor.tenant_id,
                thread_id=thread.thread_id,
                kind=WorkFeedEventKind.ROUTING_CLARIFICATION,
                payload=RoutingEventPayload(
                    disposition=routing.disposition.value,
                    suggestion_count=len(routing.suggestions),
                ),
                occurred_at=now,
                event_id=self._new_id(),
            )
            return None, router_messages
        assert routing.canonical_question is not None
        investigation = Investigation.create(
            investigation_id=self._new_id(),
            tenant_id=actor.tenant_id,
            question=routing.canonical_question,
            now=now,
            # Which data the question is asked against. Absent means the demo
            # warehouse, which is right only for a tenant that has connected
            # nothing — see `active_connection.py`.
            data_connection_id=data_connection_id,
            thread_id=thread.thread_id,
            thread_sequence=1,
            initiating_message_id=message.message_id,
        )
        investigation.start(now)
        job = ExecutionJob.create(
            job_id=self._new_id(),
            tenant_id=actor.tenant_id,
            investigation_id=investigation.investigation_id,
            now=now,
        )
        thread.title = deterministic_thread_title(routing.canonical_question)
        thread.activate(now)
        await unit_of_work.investigations.add(investigation)
        await unit_of_work.jobs.add_job(job)
        await unit_of_work.outbox.enqueue(investigation.events)
        await unit_of_work.threads.save_thread(thread)
        await unit_of_work.work_feed.append(
            tenant_id=actor.tenant_id,
            thread_id=thread.thread_id,
            kind=WorkFeedEventKind.ROUTING_RESOLVED,
            payload=RoutingEventPayload(disposition=routing.disposition.value),
            occurred_at=now,
            event_id=self._new_id(),
        )
        await unit_of_work.work_feed.append(
            tenant_id=actor.tenant_id,
            thread_id=thread.thread_id,
            kind=WorkFeedEventKind.INVESTIGATION_QUEUED,
            payload=InvestigationEventPayload(
                investigation_id=investigation.investigation_id,
                status="queued",
            ),
            occurred_at=now,
            event_id=self._new_id(),
        )
        return investigation.investigation_id, ()

    def _router_messages(
        self,
        thread: InvestigationThread,
        routing: RoutingResult,
        now: datetime,
    ) -> tuple[ThreadMessage, ...]:
        if routing.clarification is None:
            return ()
        suggestions = "\n".join(f"- {question}" for question in routing.suggestions)
        return (
            ThreadMessage.create(
                message_id=self._new_id(),
                thread_id=thread.thread_id,
                tenant_id=thread.tenant_id,
                author_id=None,
                kind=ThreadMessageKind.ROUTER_CLARIFICATION,
                content=f"{routing.clarification}\n{suggestions}",
                now=now,
            ),
        )

    async def _require_writable_project(
        self, unit_of_work: ThreadUnitOfWork, project_id: UUID
    ) -> None:
        project = require_project(
            await unit_of_work.organization.get_project(project_id)
        )
        group = await unit_of_work.organization.get_group(project.group_id)
        if group is None:
            raise ThreadNotFoundError("Project was not found")
        if project.archived_at is not None or group.archived_at is not None:
            raise ThreadConflictError(
                "Archived Groups and Projects cannot accept Thread messages"
            )

    def _uow(self, actor: AuthenticatedActor):
        return self._unit_of_work_factory(
            actor.tenant_id, actor.trace_id, actor.span_id
        )

    @staticmethod
    def _require_mutator(actor: AuthenticatedActor) -> None:
        if actor.role not in THREAD_MUTATOR_ROLES:
            raise PermissionDeniedError("This membership cannot change Threads")

    @staticmethod
    def _require_thread(thread: InvestigationThread | None) -> InvestigationThread:
        if thread is None:
            raise ThreadNotFoundError("Thread was not found")
        return thread
