"""Hiding a table, or one field within it, from the agent system.

Split from ``service.py`` for the same reason as ``catalog_reads.py`` and
``uploads.py``: the service crossed the repository's 600-line limit once this
resource group landed in it. A mixin rather than a collaborator because every
method here needs the same tenant-scoping, source-loading and role-gating
rules the rest of the service applies.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from zentra_domain_connector import (
    AccessOverrides,
    CatalogAccessOverride,
    CatalogVersion,
)

from .dto import WRITE_ROLES, AgentAccessView, AuthenticatedActor
from .views import to_access_view


class AgentAccessOperations:
    """The agent-visibility half of ``ConnectorService``."""

    async def agent_visible_catalog(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> CatalogVersion:
        """The latest Catalog Version with every hidden table and field dropped.

        The single call anything building an agent-facing view of this source
        should make. ``latest_catalog`` returns what was harvested, which is
        the right answer for a human browsing the Datasets page and the wrong
        one for the semantic layer: a table a Tenant turned off must be absent
        from what agents can reach, not merely dimmed in a UI.
        """
        version = await self.latest_catalog(actor, data_source_id)
        overrides = await self._access.list_for_source(
            data_source_id, tenant_id=actor.tenant_id
        )
        return AccessOverrides.build(data_source_id, tuple(overrides)).apply(version)

    async def _record_access(
        self,
        actor: AuthenticatedActor,
        data_source_id: UUID,
        table_name: str,
        field_name: str | None,
        *,
        agent_visible: bool,
    ) -> AgentAccessView:
        """Shared by the table- and field-level toggles below.

        Governance, not browsing — same roles as confirming a Relation.
        """
        self._require(actor, WRITE_ROLES)
        await self._load_source(actor, data_source_id)
        override = CatalogAccessOverride(
            override_id=uuid4(),
            tenant_id=actor.tenant_id,
            data_source_id=data_source_id,
            table_name=table_name,
            field_name=field_name,
            agent_visible=agent_visible,
            decided_by=actor.user_id,
            decided_at=self._clock.now(),
        )
        await self._access.upsert(override)
        return to_access_view(override)

    async def set_table_agent_access(
        self,
        actor: AuthenticatedActor,
        data_source_id: UUID,
        table_name: str,
        *,
        agent_visible: bool,
    ) -> AgentAccessView:
        return await self._record_access(
            actor, data_source_id, table_name, None, agent_visible=agent_visible
        )

    async def set_field_agent_access(
        self,
        actor: AuthenticatedActor,
        data_source_id: UUID,
        table_name: str,
        field_name: str,
        *,
        agent_visible: bool,
    ) -> AgentAccessView:
        return await self._record_access(
            actor, data_source_id, table_name, field_name, agent_visible=agent_visible
        )

    async def list_agent_access(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> tuple[AgentAccessView, ...]:
        """Every override on this source, for a caller merging them into a catalog view.

        A read, so any Tenant member may take it — the same reasoning that
        makes browsing a Relation proposal open while confirming it is not.
        """
        await self._load_source(actor, data_source_id)
        overrides = await self._access.list_for_source(
            data_source_id, tenant_id=actor.tenant_id
        )
        return tuple(to_access_view(o) for o in overrides)
