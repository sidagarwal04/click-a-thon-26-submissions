"""Turning domain entities into the read models that cross the API boundary.

Gathered here rather than as methods on the entities, so that the domain stays
unaware of what a caller is allowed to see — and so that the credential
redaction has exactly one implementation to audit.
"""

from __future__ import annotations

from zentra_domain_connector import (
    COMPOSITE_KEY_LIMITATION,
    CatalogAccessOverride,
    DataSource,
    HarvestRun,
    Relation,
)

from .dto import AgentAccessView, HarvestStatus, RelationView, SourceSummary


def to_summary(source: DataSource) -> SourceSummary:
    """The safe view of a Data Source.

    ``connection_hint`` carries host and database only. Enough for an admin to
    tell two sources apart; never the username, and never anything derived from
    the password.
    """
    host = source.metadata.get("host")
    database = source.metadata.get("database")
    hint = f"{host}/{database}" if host and database else None
    return SourceSummary(
        data_source_id=source.data_source_id,
        name=source.name,
        kind=source.kind,
        health=source.health,
        description=source.description,
        store_sample_values=source.store_sample_values,
        last_verified_at=source.last_verified_at,
        last_harvested_at=source.last_harvested_at,
        created_at=source.created_at,
        connection_hint=hint,
    )


def to_status(
    run: HarvestRun,
    *,
    unreadable: tuple[tuple[str, str], ...] = (),
) -> HarvestStatus:
    return HarvestStatus(
        harvest_run_id=run.harvest_run_id,
        data_source_id=run.data_source_id,
        phase=run.phase,
        tables_found=run.tables_found,
        fields_described=run.fields_described,
        fields_profiled=run.fields_profiled,
        relations_proposed=run.relations_proposed,
        unreadable_count=run.unreadable_count,
        queries_used=run.budget.queries_used,
        queries_budget=run.budget.max_queries,
        seconds_used=run.budget.seconds_used,
        started_at=run.started_at,
        finished_at=run.finished_at,
        catalog_version_id=run.catalog_version_id,
        failure_code=run.failure_code,
        failure_message=run.failure_message,
        unreadable=unreadable,
        fields_unexamined=run.fields_unexamined,
        unexamined_reasons=dict(run.unexamined_reasons),
        limitations=(COMPOSITE_KEY_LIMITATION,),
    )


def to_access_view(override: CatalogAccessOverride) -> AgentAccessView:
    return AgentAccessView(
        override_id=override.override_id,
        data_source_id=override.data_source_id,
        table_name=override.table_name,
        field_name=override.field_name,
        agent_visible=override.agent_visible,
        decided_by=override.decided_by,
        decided_at=override.decided_at,
    )


def to_relation_view(relation: Relation) -> RelationView:
    """A Relation with its reasoning attached.

    The evidence dictionary is flattened rather than nested so that a reviewer
    reading the API response sees every number that went into the confidence
    without having to navigate for it.
    """
    evidence: dict[str, float | int] = {}
    if relation.evidence is not None:
        e = relation.evidence
        evidence = {
            "name_affinity": e.name_affinity,
            "overlap_fraction": e.overlap_fraction,
            "sampled_rows": e.sampled_rows,
            "left_distinct": e.left_distinct,
            "right_distinct": e.right_distinct,
            "matched_distinct": e.matched_distinct,
            "raw_score": e.raw_score,
            "sample_ceiling": e.sample_ceiling,
            "cardinality_ceiling": e.cardinality_ceiling,
        }
    return RelationView(
        relation_id=relation.relation_id,
        state=relation.state,
        origin=relation.origin,
        confidence=relation.confidence,
        binding_ceiling=relation.binding_ceiling,
        cardinality=relation.cardinality,
        left=str(relation.left_identity),
        right=str(relation.right_identity),
        left_field_id=relation.left_field_id,
        right_field_id=relation.right_field_id,
        is_cross_source=relation.is_cross_source,
        evidence=evidence,
        rejection_reason=relation.rejection_reason,
        stale_reason=relation.stale_reason.value if relation.stale_reason else None,
        decided_at=relation.decided_at,
    )
