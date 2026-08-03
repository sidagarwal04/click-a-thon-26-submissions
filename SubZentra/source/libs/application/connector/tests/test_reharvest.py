"""What a re-harvest does to work a human already did.

Two behaviours pull against each other and both are wanted: a routine
re-harvest must not force re-review, and a real schema change must withdraw the
joins it invalidated. Field identity is what resolves the tension, so these
tests drive schema changes through the service and assert on which side of that
line each one falls.
"""

from __future__ import annotations

from zentra_domain_connector import RelationState, StaleReason

from .conftest import CREDENTIALS, Harness, field_descriptor, load_tpch_subset


async def _harvest(harness: Harness, actor, source_id):
    started = await harness.service.start_harvest(actor, source_id)
    status = await harness.service.run_harvest(actor, started.harvest_run_id)
    assert status.catalog_version_id is not None
    return status.catalog_version_id


async def _confirmed_tpch(harness: Harness, admin):
    load_tpch_subset(harness.connector)
    source = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    version_one = await _harvest(harness, admin, source.data_source_id)
    proposal = (await harness.service.list_relations(admin, version_one))[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)
    return source, version_one, proposal


async def test_a_reharvest_creates_a_new_version_and_keeps_the_old(
    harness: Harness, admin
) -> None:
    source, version_one, _ = await _confirmed_tpch(harness, admin)

    version_two = await _harvest(harness, admin, source.data_source_id)

    assert version_two != version_one
    assert await harness.service.get_catalog(admin, version_one) is not None


async def test_an_unchanged_schema_carries_the_confirmation_forward(
    harness: Harness, admin
) -> None:
    """Routine re-harvests must not make a reviewer redo settled work."""
    source, _, _ = await _confirmed_tpch(harness, admin)

    version_two = await _harvest(harness, admin, source.data_source_id)

    graph = await harness.service.join_graph(admin, version_two)
    assert len(graph.relations) == 1
    assert graph.relations[0].state is RelationState.CONFIRMED


async def test_a_dropped_table_stales_the_confirmation(
    harness: Harness, admin
) -> None:
    source, _, _ = await _confirmed_tpch(harness, admin)
    del harness.connector.tables["customer"]
    del harness.connector.table_meta["customer"]

    version_two = await _harvest(harness, admin, source.data_source_id)

    relations = await harness.service.list_relations(admin, version_two)
    stale = [r for r in relations if r.state is RelationState.STALE]
    assert len(stale) == 1
    assert stale[0].stale_reason == StaleReason.TABLE_DROPPED.value


async def test_a_dropped_field_stales_the_confirmation(
    harness: Harness, admin
) -> None:
    source, _, _ = await _confirmed_tpch(harness, admin)
    harness.connector.tables["customer"] = [
        f for f in harness.connector.tables["customer"] if f.name != "c_custkey"
    ]

    version_two = await _harvest(harness, admin, source.data_source_id)

    relations = await harness.service.list_relations(admin, version_two)
    stale = [r for r in relations if r.state is RelationState.STALE]
    assert len(stale) == 1
    assert stale[0].stale_reason == StaleReason.FIELD_DROPPED.value


async def test_a_type_change_stales_the_confirmation(
    harness: Harness, admin
) -> None:
    """Same name, different type: the field a reviewer confirmed is not this one."""
    source, _, _ = await _confirmed_tpch(harness, admin)
    import dataclasses

    harness.connector.tables["customer"] = [
        dataclasses.replace(f, declared_type="String")
        if f.name == "c_custkey"
        else f
        for f in harness.connector.tables["customer"]
    ]

    version_two = await _harvest(harness, admin, source.data_source_id)

    relations = await harness.service.list_relations(admin, version_two)
    stale = [r for r in relations if r.state is RelationState.STALE]
    assert len(stale) == 1
    assert stale[0].stale_reason == StaleReason.FIELD_TYPE_CHANGED.value


async def test_a_stale_relation_is_excluded_from_the_join_graph(
    harness: Harness, admin
) -> None:
    """The point of staling: an agent must stop joining on it immediately."""
    source, _, _ = await _confirmed_tpch(harness, admin)
    del harness.connector.tables["customer"]
    del harness.connector.table_meta["customer"]

    version_two = await _harvest(harness, admin, source.data_source_id)

    graph = await harness.service.join_graph(admin, version_two)
    assert graph.is_empty


async def test_an_agent_may_not_join_on_a_staled_relation(
    harness: Harness, admin
) -> None:
    source, _, proposal = await _confirmed_tpch(harness, admin)
    del harness.connector.tables["customer"]
    del harness.connector.table_meta["customer"]
    version_two = await _harvest(harness, admin, source.data_source_id)

    permitted = await harness.service.permits_join(
        admin,
        catalog_version_id=version_two,
        left_field_id=proposal.left_field_id,
        right_field_id=proposal.right_field_id,
    )

    assert permitted is False


async def test_a_stale_relation_can_be_reconfirmed_in_one_action(
    harness: Harness, admin
) -> None:
    """Recovery is confirmation, not rediscovery."""
    source, _, _ = await _confirmed_tpch(harness, admin)
    del harness.connector.tables["customer"]
    del harness.connector.table_meta["customer"]
    version_two = await _harvest(harness, admin, source.data_source_id)
    stale = [
        r
        for r in await harness.service.list_relations(admin, version_two)
        if r.state is RelationState.STALE
    ][0]

    restored = await harness.service.confirm_relation(admin, stale.relation_id)

    assert restored.state is RelationState.CONFIRMED


async def test_a_rejected_relation_is_not_reproposed(
    harness: Harness, admin
) -> None:
    """A reviewer should not be shown the same wrong guess every week."""
    from zentra_domain_connector import RejectionReason

    load_tpch_subset(harness.connector)
    source = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    version_one = await _harvest(harness, admin, source.data_source_id)
    proposal = (await harness.service.list_relations(admin, version_one))[0]
    await harness.service.reject_relation(
        admin, proposal.relation_id, reason=RejectionReason.COINCIDENTAL_OVERLAP
    )

    version_two = await _harvest(harness, admin, source.data_source_id)

    proposals = [
        r
        for r in await harness.service.list_relations(admin, version_two)
        if r.state is RelationState.PROPOSED
    ]
    assert proposals == []


async def test_a_diff_reports_what_the_upstream_team_changed(
    harness: Harness, admin
) -> None:
    source, version_one, _ = await _confirmed_tpch(harness, admin)
    harness.connector.tables["customer"] = [
        *harness.connector.tables["customer"],
        field_descriptor("c_segment", "String", 3),
    ]
    version_two = await _harvest(harness, admin, source.data_source_id)

    report = await harness.service.diff_catalog(
        admin, previous_id=version_one, current_id=version_two
    )

    assert report.added_fields == 1
    assert report.removed_fields == 0
    assert report.carried_forward == 1


async def test_a_confirmed_relation_points_at_the_new_versions_fields(
    harness: Harness, admin
) -> None:
    """Row ids change every harvest; a carried-forward Relation must follow."""
    source, _, original = await _confirmed_tpch(harness, admin)

    version_two = await _harvest(harness, admin, source.data_source_id)

    graph = await harness.service.join_graph(admin, version_two)
    carried = graph.relations[0]
    catalog = await harness.service.get_catalog(admin, version_two)
    live_ids = {f.field_id for t in catalog.tables for f in t.fields}
    assert carried.left_field_id in live_ids
    assert carried.right_field_id in live_ids
    assert carried.left_field_id != original.left_field_id
