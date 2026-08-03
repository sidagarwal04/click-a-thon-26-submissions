"""The registry read path.

`0005` deliberately keeps a pre-rename `insight_root_cause` row alive so old
Investigations stay readable. That makes this the one place a legacy role can
re-enter the running system: the Orchestrator writes the roles it is offered
into the task ledger, and the ledger is persisted. The recorder's guard checks
`execution.role` and would never see it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from zentra_domain_agent_execution import AgentRole

from zentra_api.registry import PostgresAgentRegistry


class Result:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class Connection:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    async def execute(self, *_: object) -> Result:
        return Result(self._rows)

    async def __aenter__(self) -> Connection:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


class Engine:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def connect(self) -> Connection:
        return Connection(self._rows)


class Database:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.engine = Engine(rows)


def row(agent_id: str, role: str) -> SimpleNamespace:
    return SimpleNamespace(agent_id=agent_id, role=role, version="1")


@pytest.mark.asyncio
async def test_a_legacy_role_row_is_never_advertised() -> None:
    registry = PostgresAgentRegistry(
        Database(  # type: ignore[arg-type]
            [
                row("cube_analyst_v1", "cube_analyst"),
                row("insight_v0", "insight_root_cause"),
                row("evaluator_v1", "evaluator"),
            ]
        )
    )

    agents = await registry.enabled_agents()

    assert [agent.role for agent in agents] == [
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
    ]


@pytest.mark.asyncio
async def test_the_canonical_insight_role_is_advertised() -> None:
    registry = PostgresAgentRegistry(
        Database([row("insight_v1", "insight")])  # type: ignore[arg-type]
    )

    agents = await registry.enabled_agents()

    assert [agent.role for agent in agents] == [AgentRole.INSIGHT]
