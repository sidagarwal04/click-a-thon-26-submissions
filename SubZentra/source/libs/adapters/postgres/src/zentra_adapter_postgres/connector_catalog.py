"""Persistence for Catalog Versions, Relations and Harvest Runs.

Split from `connector.py` so neither file grows past the repository's limit, and
because these three are the harvest half of the Connector: a Data Source can be
registered and used without any of them.

The serialisation here is deliberately explicit rather than reflective. A
`CatalogVersion` is immutable and stored whole, so its JSON shape is a stored
format with the compatibility obligations that implies — reading it back through
`dataclasses.asdict` would let a field rename silently orphan every row already
written.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from zentra_domain_connector import (
    BindingCeiling,
    Cardinality,
    CatalogVersion,
    FieldIdentity,
    FieldProfile,
    HarvestBudget,
    HarvestPhase,
    HarvestRun,
    HarvestScope,
    RejectionReason,
    Relation,
    RelationEvidence,
    RelationOrigin,
    RelationState,
    SourceField,
    SourceTable,
    StaleReason,
    TypeFamily,
    UnreadableTable,
)

from .database import Database
from .schema_connector import catalog_versions, harvest_runs, relations

# --------------------------------------------------------------- catalog JSON


def _profile_to_json(profile: FieldProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "sampled_rows": profile.sampled_rows,
        "null_fraction": profile.null_fraction,
        "distinct_count": profile.distinct_count,
        "min_value": profile.min_value,
        "max_value": profile.max_value,
        "sample_values": list(profile.sample_values),
    }


def _profile_from_json(data: dict[str, Any] | None) -> FieldProfile | None:
    if data is None:
        return None
    return FieldProfile(
        sampled_rows=data["sampled_rows"],
        null_fraction=data.get("null_fraction"),
        distinct_count=data.get("distinct_count"),
        min_value=data.get("min_value"),
        max_value=data.get("max_value"),
        sample_values=tuple(data.get("sample_values") or ()),
    )


def _field_to_json(source_field: SourceField) -> dict[str, Any]:
    return {
        "field_id": str(source_field.field_id),
        "table_id": str(source_field.table_id),
        "name": source_field.name,
        "declared_type": source_field.declared_type,
        "family": source_field.family.value,
        "normalised_type": source_field.normalised_type,
        "nullable": source_field.nullable,
        "position": source_field.position,
        "profile": _profile_to_json(source_field.profile),
    }


def _field_from_json(data: dict[str, Any]) -> SourceField:
    return SourceField(
        field_id=UUID(data["field_id"]),
        table_id=UUID(data["table_id"]),
        name=data["name"],
        declared_type=data["declared_type"],
        family=TypeFamily(data["family"]),
        normalised_type=data["normalised_type"],
        nullable=data["nullable"],
        position=data["position"],
        profile=_profile_from_json(data.get("profile")),
    )


def _table_to_json(table: SourceTable) -> dict[str, Any]:
    return {
        "table_id": str(table.table_id),
        "name": table.name,
        "database": table.database,
        "engine": table.engine,
        "estimated_rows": table.estimated_rows,
        "size_bytes": table.size_bytes,
        "fields": [_field_to_json(f) for f in table.fields],
    }


def _table_from_json(data: dict[str, Any]) -> SourceTable:
    return SourceTable(
        table_id=UUID(data["table_id"]),
        name=data["name"],
        database=data["database"],
        engine=data.get("engine"),
        estimated_rows=data.get("estimated_rows"),
        size_bytes=data.get("size_bytes"),
        fields=tuple(_field_from_json(f) for f in data.get("fields") or ()),
    )


def _catalog_payload(version: CatalogVersion) -> dict[str, Any]:
    return {
        "tables": [_table_to_json(t) for t in version.tables],
        "unreadable": [
            {"qualified_name": u.qualified_name, "reason": u.reason}
            for u in version.unreadable
        ],
    }


class PostgresCatalogRepository:
    """`CatalogRepository` over Postgres.

    There is no `save`: a Catalog Version is immutable once written, and the
    port does not offer one.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def add_version(self, version: CatalogVersion) -> None:
        async with self._database.tenant_connection(version.tenant_id) as connection:
            await connection.execute(
                insert(catalog_versions).values(
                    catalog_version_id=version.catalog_version_id,
                    tenant_id=version.tenant_id,
                    data_source_id=version.data_source_id,
                    harvest_run_id=version.harvest_run_id,
                    created_at=version.created_at,
                    payload=_catalog_payload(version),
                )
            )

    def _to_entity(self, row: Any) -> CatalogVersion:
        payload = row.payload or {}
        return CatalogVersion(
            catalog_version_id=row.catalog_version_id,
            data_source_id=row.data_source_id,
            tenant_id=row.tenant_id,
            harvest_run_id=row.harvest_run_id,
            created_at=row.created_at,
            tables=tuple(_table_from_json(t) for t in payload.get("tables") or ()),
            unreadable=tuple(
                UnreadableTable(
                    qualified_name=u["qualified_name"], reason=u["reason"]
                )
                for u in payload.get("unreadable") or ()
            ),
        )

    async def get_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None:
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(catalog_versions).where(
                        catalog_versions.c.catalog_version_id == catalog_version_id,
                        catalog_versions.c.tenant_id == tenant_id,
                    )
                )
            ).one_or_none()
        return None if row is None else self._to_entity(row)

    async def latest_version(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None:
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(catalog_versions)
                    .where(
                        catalog_versions.c.data_source_id == data_source_id,
                        catalog_versions.c.tenant_id == tenant_id,
                    )
                    .order_by(catalog_versions.c.created_at.desc())
                    .limit(1)
                )
            ).one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_versions(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogVersion]:
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(catalog_versions)
                    .where(
                        catalog_versions.c.data_source_id == data_source_id,
                        catalog_versions.c.tenant_id == tenant_id,
                    )
                    .order_by(catalog_versions.c.created_at.desc())
                )
            ).all()
        return [self._to_entity(row) for row in rows]


# ------------------------------------------------------------- relation rows


def _identity_to_json(identity: FieldIdentity) -> dict[str, str]:
    return {
        "table_name": identity.table_name,
        "field_name": identity.field_name,
        "normalised_type": identity.normalised_type,
    }


def _identity_from_json(data: dict[str, str]) -> FieldIdentity:
    return FieldIdentity(
        table_name=data["table_name"],
        field_name=data["field_name"],
        normalised_type=data["normalised_type"],
    )


def _evidence_to_json(evidence: RelationEvidence | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "name_affinity": evidence.name_affinity,
        "overlap_fraction": evidence.overlap_fraction,
        "sampled_rows": evidence.sampled_rows,
        "left_distinct": evidence.left_distinct,
        "right_distinct": evidence.right_distinct,
        "matched_distinct": evidence.matched_distinct,
        "raw_score": evidence.raw_score,
        "sample_ceiling": evidence.sample_ceiling,
        "cardinality_ceiling": evidence.cardinality_ceiling,
    }


def _evidence_from_json(data: dict[str, Any] | None) -> RelationEvidence | None:
    return None if data is None else RelationEvidence(**data)


def _relation_values(relation: Relation) -> dict[str, Any]:
    """Everything a decision may change. Identity and sides are not here."""
    return {
        "state": relation.state.value,
        "origin": relation.origin.value,
        "confidence": relation.confidence,
        "binding_ceiling": relation.binding_ceiling.value,
        "cardinality": relation.cardinality.value,
        "evidence": _evidence_to_json(relation.evidence),
        "decided_at": relation.decided_at,
        "decided_by": relation.decided_by,
        "rejection_reason": (
            relation.rejection_reason.value if relation.rejection_reason else None
        ),
        "stale_reason": (
            relation.stale_reason.value if relation.stale_reason else None
        ),
        "relation_metadata": dict(relation.metadata),
    }


def _relation_from_row(row: Any) -> Relation:
    return Relation(
        relation_id=row.relation_id,
        tenant_id=row.tenant_id,
        catalog_version_id=row.catalog_version_id,
        left_field_id=row.left_field_id,
        right_field_id=row.right_field_id,
        left_identity=_identity_from_json(row.left_identity),
        right_identity=_identity_from_json(row.right_identity),
        left_data_source_id=row.left_data_source_id,
        right_data_source_id=row.right_data_source_id,
        state=RelationState(row.state),
        origin=RelationOrigin(row.origin),
        confidence=row.confidence,
        binding_ceiling=BindingCeiling(row.binding_ceiling),
        cardinality=Cardinality(row.cardinality),
        evidence=_evidence_from_json(row.evidence),
        decided_at=row.decided_at,
        decided_by=row.decided_by,
        rejection_reason=(
            RejectionReason(row.rejection_reason) if row.rejection_reason else None
        ),
        stale_reason=StaleReason(row.stale_reason) if row.stale_reason else None,
        created_at=row.created_at,
        metadata=dict(row.relation_metadata or {}),
    )


class PostgresRelationRepository:
    """`RelationRepository` over Postgres."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def add_many(self, proposals: Sequence[Relation]) -> None:
        if not proposals:
            return
        # Every relation in one batch belongs to one harvest, so one tenant.
        tenant_id = proposals[0].tenant_id
        async with self._database.tenant_connection(tenant_id) as connection:
            await connection.execute(
                insert(relations),
                [
                    {
                        "relation_id": relation.relation_id,
                        "tenant_id": relation.tenant_id,
                        "catalog_version_id": relation.catalog_version_id,
                        "left_field_id": relation.left_field_id,
                        "right_field_id": relation.right_field_id,
                        "left_identity": _identity_to_json(relation.left_identity),
                        "right_identity": _identity_to_json(relation.right_identity),
                        "left_data_source_id": relation.left_data_source_id,
                        "right_data_source_id": relation.right_data_source_id,
                        "created_at": relation.created_at,
                        **_relation_values(relation),
                    }
                    for relation in proposals
                ],
            )

    async def get(self, relation_id: UUID, *, tenant_id: UUID) -> Relation | None:
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(relations).where(
                        relations.c.relation_id == relation_id,
                        relations.c.tenant_id == tenant_id,
                    )
                )
            ).one_or_none()
        return None if row is None else _relation_from_row(row)

    async def save(self, relation: Relation) -> None:
        async with self._database.tenant_connection(relation.tenant_id) as connection:
            await connection.execute(
                update(relations)
                .where(
                    relations.c.relation_id == relation.relation_id,
                    relations.c.tenant_id == relation.tenant_id,
                )
                .values(**_relation_values(relation))
            )

    async def list_for_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]:
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(relations).where(
                        relations.c.catalog_version_id == catalog_version_id,
                        relations.c.tenant_id == tenant_id,
                    )
                )
            ).all()
        return [_relation_from_row(row) for row in rows]

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]:
        """Relations touching this source from either side.

        A cross-source Relation belongs to both of the sources it joins, so
        matching only the left would hide half of them from the source that
        sits on the right.
        """
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(relations).where(
                        relations.c.tenant_id == tenant_id,
                        (relations.c.left_data_source_id == data_source_id)
                        | (relations.c.right_data_source_id == data_source_id),
                    )
                )
            ).all()
        return [_relation_from_row(row) for row in rows]


# ----------------------------------------------------------------- harvest runs


def _run_values(run: HarvestRun) -> dict[str, Any]:
    return {
        "phase": run.phase.value,
        "scope": {
            "databases": list(run.scope.databases),
            "tables": list(run.scope.tables),
        },
        "budget": {
            "max_queries": run.budget.max_queries,
            "max_seconds": run.budget.max_seconds,
            "sample_rows": run.budget.sample_rows,
            "queries_used": run.budget.queries_used,
            "seconds_used": run.budget.seconds_used,
        },
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "tables_found": run.tables_found,
        "fields_described": run.fields_described,
        "fields_profiled": run.fields_profiled,
        "relations_proposed": run.relations_proposed,
        "unreadable_count": run.unreadable_count,
        "catalog_version_id": run.catalog_version_id,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "cancellation_requested": run.cancellation_requested,
    }


def _run_from_row(row: Any) -> HarvestRun:
    scope = row.scope or {}
    budget = row.budget or {}
    return HarvestRun(
        harvest_run_id=row.harvest_run_id,
        data_source_id=row.data_source_id,
        tenant_id=row.tenant_id,
        phase=HarvestPhase(row.phase),
        scope=HarvestScope(
            databases=tuple(scope.get("databases") or ()),
            tables=tuple(scope.get("tables") or ()),
        ),
        budget=HarvestBudget(**budget) if budget else HarvestBudget(),
        started_at=row.started_at,
        finished_at=row.finished_at,
        tables_found=row.tables_found,
        fields_described=row.fields_described,
        fields_profiled=row.fields_profiled,
        relations_proposed=row.relations_proposed,
        unreadable_count=row.unreadable_count,
        catalog_version_id=row.catalog_version_id,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        cancellation_requested=row.cancellation_requested,
    )


class PostgresHarvestRunRepository:
    """`HarvestRunRepository` over Postgres."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def add(self, run: HarvestRun) -> None:
        async with self._database.tenant_connection(run.tenant_id) as connection:
            await connection.execute(
                insert(harvest_runs).values(
                    harvest_run_id=run.harvest_run_id,
                    tenant_id=run.tenant_id,
                    data_source_id=run.data_source_id,
                    **_run_values(run),
                )
            )

    async def get(self, harvest_run_id: UUID, *, tenant_id: UUID) -> HarvestRun | None:
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(harvest_runs).where(
                        harvest_runs.c.harvest_run_id == harvest_run_id,
                        harvest_runs.c.tenant_id == tenant_id,
                    )
                )
            ).one_or_none()
        return None if row is None else _run_from_row(row)

    async def save(self, run: HarvestRun) -> None:
        async with self._database.tenant_connection(run.tenant_id) as connection:
            await connection.execute(
                update(harvest_runs)
                .where(
                    harvest_runs.c.harvest_run_id == run.harvest_run_id,
                    harvest_runs.c.tenant_id == run.tenant_id,
                )
                .values(**_run_values(run))
            )

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[HarvestRun]:
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(harvest_runs)
                    .where(
                        harvest_runs.c.data_source_id == data_source_id,
                        harvest_runs.c.tenant_id == tenant_id,
                    )
                    .order_by(harvest_runs.c.started_at.desc().nullslast())
                )
            ).all()
        return [_run_from_row(row) for row in rows]

    async def active_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> HarvestRun | None:
        """The run still in flight, if there is one.

        Non-terminal is expressed as a `NOT IN` over the terminal phases rather
        than a list of running ones: a phase added later is running until
        something says otherwise, and defaulting the other way would let a
        second harvest start alongside it.
        """
        terminal = (
            HarvestPhase.COMPLETED.value,
            HarvestPhase.FAILED.value,
            HarvestPhase.CANCELLED.value,
        )
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(harvest_runs)
                    .where(
                        harvest_runs.c.data_source_id == data_source_id,
                        harvest_runs.c.tenant_id == tenant_id,
                        harvest_runs.c.phase.notin_(terminal),
                    )
                    .limit(1)
                )
            ).one_or_none()
        return None if row is None else _run_from_row(row)


__all__ = [
    "PostgresCatalogRepository",
    "PostgresHarvestRunRepository",
    "PostgresRelationRepository",
]
