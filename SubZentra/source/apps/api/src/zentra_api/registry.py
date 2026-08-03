from __future__ import annotations

from sqlalchemy import select
from zentra_adapter_postgres import Database
from zentra_adapter_postgres.schema import agent_registry
from zentra_domain_agent_execution import (
    LEGACY_ROLES,
    AgentCapability,
    AgentRole,
    PublicAgent,
    RegisteredAgent,
)

_PUBLIC_DEFAULTS: dict[AgentRole, tuple[str, str, tuple[AgentCapability, ...]]] = {
    AgentRole.ORCHESTRATOR: (
        "Orchestrator",
        "Plans governed analytical work and delegates it to registered Agents.",
        (
            AgentCapability(
                capability_id="plan_investigation",
                version="1.0",
                display_name="Plan investigation",
                description="Creates a bounded plan over registered analytical roles.",
            ),
        ),
    ),
    AgentRole.CUBE_ANALYST: (
        "Cube Analyst",
        "Queries governed Semantic Metrics without raw SQL authority.",
        (
            AgentCapability(
                capability_id="query_semantic_metrics",
                version="1.0",
                display_name="Query semantic metrics",
                description=(
                    "Executes a governed query plan through the semantic layer."
                ),
            ),
        ),
    ),
    AgentRole.EVALUATOR: (
        "Evaluator",
        "Independently rechecks analytical evidence and validation conditions.",
        (
            AgentCapability(
                capability_id="validate_evidence",
                version="1.0",
                display_name="Validate evidence",
                description="Rechecks measurements and returns typed validation.",
            ),
        ),
    ),
    AgentRole.INSIGHT: (
        "Insight Agent",
        "Synthesizes validated evidence into a cited Draft Finding.",
        (
            AgentCapability(
                capability_id="draft_finding",
                version="1.0",
                display_name="Draft finding",
                description="Creates cited observed and interpretation claims.",
            ),
        ),
    ),
}


class PostgresAgentRegistry:
    """Which agents exist is a table, not a code list (ADR-002).

    The database constraint already forbids `enabled` without a passing eval,
    so disabling a misbehaving agent is a row update rather than a deploy.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def enabled_agents(self) -> tuple[RegisteredAgent, ...]:
        async with self._database.engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(
                        agent_registry.c.agent_id,
                        agent_registry.c.role,
                        agent_registry.c.version,
                    ).where(agent_registry.c.enabled.is_(True))
                )
            ).all()
        agents = (
            RegisteredAgent(
                agent_id=row.agent_id,
                role=AgentRole(row.role),
                version=row.version,
            )
            for row in rows
        )
        # A legacy row is readable but must never be planned against. The
        # Orchestrator writes the roles it is offered into the task ledger,
        # and that ledger is persisted — so advertising one here would write
        # the legacy value back out through a path the recorder's guard never
        # sees. `0005` keeps such rows alive deliberately; this is where they
        # stop.
        return tuple(agent for agent in agents if agent.role not in LEGACY_ROLES)

    async def public_agents(self) -> tuple[PublicAgent, ...]:
        async with self._database.engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(
                        agent_registry.c.agent_id,
                        agent_registry.c.role,
                        agent_registry.c.version,
                        agent_registry.c.enabled,
                        agent_registry.c.eval_status,
                        agent_registry.c.display_name,
                        agent_registry.c.description,
                        agent_registry.c.capabilities,
                    ).where(
                        agent_registry.c.role.not_in([r.value for r in LEGACY_ROLES])
                    )
                )
            ).all()
        result = []
        for row in rows:
            role = AgentRole(row.role)
            default = _PUBLIC_DEFAULTS.get(role)
            display_name = row.display_name or (default[0] if default else role.value)
            description = row.description or (
                default[1] if default else "Registered ZentraOS Agent."
            )
            capabilities = tuple(
                AgentCapability.model_validate(value)
                for value in (row.capabilities or ())
            ) or (default[2] if default else ())
            result.append(
                PublicAgent(
                    agent_id=row.agent_id,
                    role=role,
                    version=row.version,
                    display_name=display_name,
                    description=description,
                    enabled=row.enabled,
                    evaluation_status=row.eval_status,
                    capabilities=capabilities,
                )
            )
        return tuple(sorted(result, key=lambda agent: agent.role.value))
