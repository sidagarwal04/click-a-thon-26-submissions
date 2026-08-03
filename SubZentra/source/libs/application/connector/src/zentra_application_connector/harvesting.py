"""Executing one Harvest Run.

Split from the service because the run body is long, phased, and has to keep
going in the face of individual failures — very different in shape from the
short request-scoped operations around it.

The ordering matters and is not arbitrary. Schema first, because it is free and
makes the catalog usable within seconds. Profiling second, because it costs
queries but each is independent. Overlap measurement last, because it is the
most expensive and the profiles are what let it be targeted at pairs already
worth measuring.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from zentra_domain_connector import (
    CatalogVersion,
    DataSource,
    FieldIdentity,
    HarvestPhase,
    HarvestRun,
    Relation,
    RelationOrigin,
    RelationState,
    SourceField,
    SourceTable,
    UnreadableTable,
    classify,
    coverage_summary,
    generate_candidates,
    normalise_type,
    reconcile,
    score_candidate,
)

from .dto import SourceCredentials
from .ports import (
    CatalogRepository,
    Clock,
    HarvestRunRepository,
    RelationRepository,
    SourceConnector,
)


@dataclass(frozen=True, slots=True)
class HarvestDependencies:
    connector: SourceConnector
    catalogs: CatalogRepository
    relations: RelationRepository
    runs: HarvestRunRepository
    clock: Clock


class _Cancelled(Exception):
    """Raised internally when a cancellation request is observed."""


async def execute_harvest(
    deps: HarvestDependencies,
    *,
    run: HarvestRun,
    source: DataSource,
    credentials: SourceCredentials,
    peer_catalogs: Sequence[tuple[UUID, CatalogVersion, SourceCredentials]] = (),
) -> CatalogVersion | None:
    """Run discovery to completion, or to the first thing that stops it.

    Returns the Catalog Version produced, or ``None`` if the run failed or was
    cancelled before one existed. Never raises for a source-side problem: a
    harvest that cannot read one table is a harvest with a gap in it, not a
    failed one, and discarding everything else learned would be the worse
    outcome.
    """
    now = deps.clock.now
    try:
        run.advance(HarvestPhase.CONNECTING, at=now())
        await deps.runs.save(run)
        _checkpoint(run)

        tables, unreadable = await _describe_tables(deps, run, credentials)
        _checkpoint(run)

        tables = await _profile_fields(
            deps, run, credentials, tables, source.store_sample_values
        )
        _checkpoint(run)

        version = CatalogVersion(
            catalog_version_id=uuid4(),
            data_source_id=source.data_source_id,
            tenant_id=source.tenant_id,
            harvest_run_id=run.harvest_run_id,
            created_at=now(),
            tables=tables,
            unreadable=unreadable,
        )
        await deps.catalogs.add_version(version)

        outcome = await _reconcile_previous(deps, source, version, at=now())
        await _infer_relations(
            deps,
            run,
            source,
            version,
            credentials,
            peer_catalogs=peer_catalogs,
            suppressed=outcome,
        )

        run.complete(catalog_version_id=version.catalog_version_id, at=now())
        await deps.runs.save(run)
        return version

    except _Cancelled:
        run.cancel(at=now())
        await deps.runs.save(run)
        return None
    except Exception as exc:  # noqa: BLE001 - a run must always reach a terminal state
        # A run whose process dies must not sit in `running` where a reader
        # cannot tell it from one that is merely slow.
        run.fail(code="harvest_failed", message=str(exc)[:500], at=now())
        await deps.runs.save(run)
        return None


def _checkpoint(run: HarvestRun) -> None:
    """Stop here if cancellation was requested.

    Between phases rather than mid-query: a run may be waiting on someone else's
    warehouse, and abandoning that connection is not ours to do abruptly.
    """
    if run.cancellation_requested:
        raise _Cancelled


async def _describe_tables(
    deps: HarvestDependencies,
    run: HarvestRun,
    credentials: SourceCredentials,
) -> tuple[tuple[SourceTable, ...], tuple[UnreadableTable, ...]]:
    run.advance(HarvestPhase.LISTING_TABLES, at=deps.clock.now())
    descriptors = await deps.connector.list_tables(
        credentials, databases=run.scope.databases
    )
    run.budget.spend(queries=1)

    in_scope = [
        d for d in descriptors if run.scope.includes_table(d.database, d.name)
    ]
    run.tables_found = len(in_scope)
    await deps.runs.save(run)

    run.advance(HarvestPhase.DESCRIBING_FIELDS, at=deps.clock.now())
    tables: list[SourceTable] = []
    unreadable: list[UnreadableTable] = []

    for descriptor in in_scope:
        _checkpoint(run)
        if run.budget.exhausted:
            break
        try:
            described = await deps.connector.describe_fields(
                credentials, database=descriptor.database, table=descriptor.name
            )
        except Exception as exc:  # noqa: BLE001 - one bad table must not end the run
            unreadable.append(
                UnreadableTable(
                    qualified_name=f"{descriptor.database}.{descriptor.name}",
                    reason=str(exc)[:200],
                )
            )
            run.unreadable_count = len(unreadable)
            await deps.runs.save(run)
            continue

        run.budget.spend(queries=1)
        table_id = uuid4()
        fields = tuple(
            SourceField(
                field_id=uuid4(),
                table_id=table_id,
                name=f.name,
                declared_type=f.declared_type,
                family=classify(f.declared_type),
                normalised_type=normalise_type(f.declared_type),
                nullable=f.nullable,
                position=f.position,
            )
            for f in described
        )
        tables.append(
            SourceTable(
                table_id=table_id,
                name=descriptor.name,
                database=descriptor.database,
                engine=descriptor.engine,
                estimated_rows=descriptor.estimated_rows,
                size_bytes=descriptor.size_bytes,
                fields=fields,
            )
        )
        run.fields_described += len(fields)
        await deps.runs.save(run)

    return tuple(tables), tuple(unreadable)


async def _profile_fields(
    deps: HarvestDependencies,
    run: HarvestRun,
    credentials: SourceCredentials,
    tables: tuple[SourceTable, ...],
    store_sample_values: bool,
) -> tuple[SourceTable, ...]:
    run.advance(HarvestPhase.PROFILING, at=deps.clock.now())
    profiled: list[SourceTable] = []

    for table in tables:
        _checkpoint(run)
        fields: list[SourceField] = []
        for source_field in table.fields:
            if run.budget.exhausted:
                fields.append(source_field)
                continue
            try:
                profile = await deps.connector.profile_field(
                    credentials,
                    database=table.database,
                    table=table.name,
                    field_name=source_field.name,
                    sample_rows=run.budget.sample_rows,
                    include_sample_values=store_sample_values,
                )
            except Exception:  # noqa: BLE001 - an unprofilable field keeps its schema
                fields.append(source_field)
                continue
            run.budget.spend(queries=1)
            run.fields_profiled += 1
            fields.append(
                SourceField(
                    field_id=source_field.field_id,
                    table_id=source_field.table_id,
                    name=source_field.name,
                    declared_type=source_field.declared_type,
                    family=source_field.family,
                    normalised_type=source_field.normalised_type,
                    nullable=source_field.nullable,
                    position=source_field.position,
                    profile=profile,
                )
            )
        profiled.append(
            SourceTable(
                table_id=table.table_id,
                name=table.name,
                database=table.database,
                engine=table.engine,
                estimated_rows=table.estimated_rows,
                size_bytes=table.size_bytes,
                fields=tuple(fields),
            )
        )
        await deps.runs.save(run)

    return tuple(profiled)


async def _reconcile_previous(
    deps: HarvestDependencies,
    source: DataSource,
    version: CatalogVersion,
    *,
    at: datetime,
) -> frozenset[frozenset[FieldIdentity]]:
    """Carry confirmed Relations onto the new version, or stale them.

    Returns the pairs a reviewer already rejected, so the inference step can
    decline to re-propose them. Someone who rejected a guess should not be shown
    it again every week.
    """
    previous = await deps.relations.list_for_source(
        source.data_source_id, tenant_id=source.tenant_id
    )
    if not previous:
        return frozenset()

    new_ids = {
        identity: source_field.field_id
        for identity, source_field in version.field_index().items()
    }
    outcome = reconcile(
        tuple(previous),
        version,
        new_catalog_version_id=version.catalog_version_id,
        at=at,
        new_field_ids=new_ids,
    )
    for relation in (*outcome.carried_forward, *outcome.staled):
        await deps.relations.save(relation)
    return outcome.suppressed_pairs


async def _infer_relations(
    deps: HarvestDependencies,
    run: HarvestRun,
    source: DataSource,
    version: CatalogVersion,
    credentials: SourceCredentials,
    *,
    peer_catalogs: Sequence[tuple[UUID, CatalogVersion, SourceCredentials]],
    suppressed: frozenset[frozenset[FieldIdentity]],
) -> None:
    """Propose Relations, spending what remains of the query budget.

    Peer catalogs are passed in whole rather than fetched here so that a
    cross-source pair is the same code path as a within-source one. Building
    cross-source inference as a special case would have meant two
    implementations that could disagree about confidence.
    """
    run.advance(HarvestPhase.INFERRING_RELATIONS, at=deps.clock.now())

    catalogs: list[tuple[UUID, CatalogVersion]] = [(source.data_source_id, version)]
    creds: dict[UUID, SourceCredentials] = {source.data_source_id: credentials}
    for peer_id, peer_version, peer_credentials in peer_catalogs:
        catalogs.append((peer_id, peer_version))
        creds[peer_id] = peer_credentials

    candidates, unexamined = generate_candidates(tuple(catalogs))
    # Recorded rather than discarded. Without it an empty proposal list is
    # indistinguishable from a schema nothing was eligible to be looked at in.
    run.fields_unexamined = len(unexamined)
    run.unexamined_reasons = coverage_summary(unexamined)
    carried = {
        r.pinned_identities
        for r in await deps.relations.list_for_source(
            source.data_source_id, tenant_id=source.tenant_id
        )
        if r.state in (RelationState.CONFIRMED, RelationState.STALE)
    }

    proposals: list[Relation] = []
    for candidate in candidates:
        _checkpoint(run)
        if run.budget.exhausted:
            break

        left_identity = candidate.left_field.identity(candidate.left_table.name)
        right_identity = candidate.right_field.identity(candidate.right_table.name)
        pair = frozenset({left_identity, right_identity})
        if pair in suppressed or pair in carried:
            continue

        try:
            overlap = await deps.connector.measure_overlap(
                creds[candidate.left_data_source_id],
                creds[candidate.right_data_source_id],
                left=(
                    candidate.left_table.database,
                    candidate.left_table.name,
                    candidate.left_field.name,
                ),
                right=(
                    candidate.right_table.database,
                    candidate.right_table.name,
                    candidate.right_field.name,
                ),
                sample_rows=run.budget.sample_rows,
            )
        except Exception:  # noqa: BLE001 - an unmeasurable pair is simply not proposed
            continue

        run.budget.spend(queries=1)
        scored = score_candidate(candidate, overlap)
        if scored is None:
            continue

        proposals.append(
            Relation(
                relation_id=uuid4(),
                tenant_id=source.tenant_id,
                catalog_version_id=version.catalog_version_id,
                left_field_id=candidate.left_field.field_id,
                right_field_id=candidate.right_field.field_id,
                left_identity=left_identity,
                right_identity=right_identity,
                left_data_source_id=candidate.left_data_source_id,
                right_data_source_id=candidate.right_data_source_id,
                state=RelationState.PROPOSED,
                origin=RelationOrigin.INFERRED,
                confidence=scored.confidence,
                binding_ceiling=scored.binding_ceiling,
                cardinality=scored.cardinality,
                evidence=scored.evidence,
                created_at=deps.clock.now(),
            )
        )

    proposals.sort(key=lambda r: r.confidence, reverse=True)
    if proposals:
        await deps.relations.add_many(proposals)
    run.relations_proposed = len(proposals)
    await deps.runs.save(run)
