"""Reading Catalog Versions and comparing them.

Split from ``service.py`` for the same reason as ``uploads.py``: the service
crossed the repository's 600-line limit once every resource group landed in it.
These four operations are all pure reads over immutable Catalog Versions, which
makes them a clean seam — nothing here mutates, and nothing here needs the
connector, cipher, or landing zone.
"""

from __future__ import annotations

from uuid import UUID

from zentra_domain_connector import CatalogVersion, RelationState, diff_catalogs

from .dto import (
    AuthenticatedActor,
    CatalogVersionNotFoundError,
    ReharvestReport,
)


class CatalogOperations:
    """The catalog-read half of ``ConnectorService``.

    Relies on the attributes the service establishes in its constructor. A mixin
    rather than a collaborator because every method here needs the same
    tenant-scoping and source-loading rules the rest of the service applies, and
    passing those to a separate object would duplicate them.
    """

    async def latest_catalog(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> CatalogVersion:
        await self._load_source(actor, data_source_id)
        version = await self._catalogs.latest_version(
            data_source_id, tenant_id=actor.tenant_id
        )
        if version is None:
            raise CatalogVersionNotFoundError(str(data_source_id))
        return version

    async def get_catalog(
        self, actor: AuthenticatedActor, catalog_version_id: UUID
    ) -> CatalogVersion:
        version = await self._catalogs.get_version(
            catalog_version_id, tenant_id=actor.tenant_id
        )
        if version is None:
            raise CatalogVersionNotFoundError(str(catalog_version_id))
        return version

    async def search_catalog(
        self, actor: AuthenticatedActor, catalog_version_id: UUID, term: str
    ) -> tuple[str, ...]:
        version = await self.get_catalog(actor, catalog_version_id)
        return tuple(
            table.name if source_field is None else f"{table.name}.{source_field.name}"
            for table, source_field in version.search(term)
        )

    async def diff_catalog(
        self,
        actor: AuthenticatedActor,
        *,
        previous_id: UUID,
        current_id: UUID,
    ) -> ReharvestReport:
        """What changed between two versions, and what it cost a reviewer.

        Reports the field-level diff alongside how many confirmations survived
        and how many went stale, because those are the same question from a
        reviewer's side: a schema change matters to them exactly insofar as it
        invalidated work they had already done.
        """
        previous = await self.get_catalog(actor, previous_id)
        current = await self.get_catalog(actor, current_id)
        diff = diff_catalogs(previous, current)
        relations = await self._relations.list_for_version(
            current_id, tenant_id=actor.tenant_id
        )
        return ReharvestReport(
            catalog_version_id=current_id,
            carried_forward=sum(
                1 for r in relations if r.state is RelationState.CONFIRMED
            ),
            staled=sum(1 for r in relations if r.state is RelationState.STALE),
            added_fields=len(diff.added),
            removed_fields=len(diff.removed),
            type_changed_fields=len(diff.type_changed),
        )
