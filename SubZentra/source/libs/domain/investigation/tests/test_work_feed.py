from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zentra_domain_investigation import (
    AgentEventPayload,
    ThreadEvent,
    WorkFeedEventKind,
)


def test_public_agent_event_rejects_reasoning_sql_and_raw_rows() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentEventPayload(
            execution_id=uuid4(),
            agent_id="cube_analyst_v1",
            role="cube_analyst",
            reasoning="hidden",
            sql="select 1",
            raw_rows=[[1]],
        )


def test_thread_event_requires_positive_resume_sequence() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        ThreadEvent(
            event_id=uuid4(),
            tenant_id=uuid4(),
            thread_id=uuid4(),
            sequence=0,
            kind=WorkFeedEventKind.AGENT_STARTED,
            occurred_at=datetime.now(UTC),
            payload=AgentEventPayload(
                execution_id=uuid4(),
                agent_id="orchestrator_v1",
                role="orchestrator",
            ),
        )
