"""Relation inference, confirmation, and the Join Graph agents may join on.

The behaviour asserted here is external: what a reviewer is offered, what
bounds a proposal's confidence, and what an agent is permitted to do. How the
score is computed internally is deliberately not asserted — the scoring rules
are the part most likely to be tuned, and tests coupled to them would obstruct
exactly the work they exist to protect.
"""

from __future__ import annotations

import pytest
from zentra_domain_connector import (
    BindingCeiling,
    OverlapMeasurement,
    RejectionReason,
    RelationOrigin,
    RelationState,
)

from zentra_application_connector import (
    ConflictError,
    PermissionDeniedError,
    RelationNotFoundError,
)

from .conftest import CREDENTIALS, Harness, descriptors, load_tpch_subset


async def _harvested(harness: Harness, actor):
    source = await harness.service.register_source(
        actor, name="Warehouse", credentials=CREDENTIALS
    )
    started = await harness.service.start_harvest(actor, source.data_source_id)
    status = await harness.service.run_harvest(actor, started.harvest_run_id)
    assert status.catalog_version_id is not None
    return source, status.catalog_version_id


async def test_a_real_foreign_key_is_proposed_without_any_schema_knowledge(
    harness: Harness, admin
) -> None:
    """ClickHouse records no foreign keys, so this must come from the data."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)

    proposals = await harness.service.list_relations(
        admin, version_id, state=RelationState.PROPOSED
    )

    assert len(proposals) == 1
    assert {proposals[0].left, proposals[0].right} == {
        "orders.o_custkey:int64",
        "customer.c_custkey:int64",
    }


async def test_a_proposal_carries_the_evidence_behind_it(
    harness: Harness, admin
) -> None:
    """A proposal that could not be argued with would be an instruction."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)

    proposal = (await harness.service.list_relations(admin, version_id))[0]

    assert proposal.evidence["overlap_fraction"] == 1.0
    assert proposal.evidence["sampled_rows"] == 1_500_000
    assert proposal.evidence["matched_distinct"] == 99_996
    assert proposal.evidence["name_affinity"] > 0


async def test_type_incompatible_pairs_are_never_proposed(
    harness: Harness, admin
) -> None:
    """A date joining a string is not a weak candidate; it is not a candidate."""
    harness.connector.tables = {
        "a": [*descriptors(["shared_id"], "DateTime")],
        "b": [*descriptors(["shared_id"], "String")],
    }
    harness.connector.overlaps = {
        ("a.shared_id", "b.shared_id"): OverlapMeasurement(
            left_distinct=5000,
            right_distinct=5000,
            matched_distinct=5000,
            sampled_rows=20000,
        )
    }
    _, version_id = await _harvested(harness, admin)

    assert await harness.service.list_relations(admin, version_id) == ()


async def test_two_boolean_columns_with_perfect_overlap_are_not_proposed(
    harness: Harness, admin
) -> None:
    """Perfect overlap on a boolean is what unrelated fields already do."""
    harness.connector.tables = {
        "a": descriptors(["is_active"], "Bool"),
        "b": descriptors(["is_active"], "Bool"),
    }
    harness.connector.overlaps = {
        ("a.is_active", "b.is_active"): OverlapMeasurement(
            left_distinct=2,
            right_distinct=2,
            matched_distinct=2,
            sampled_rows=50000,
        )
    }
    _, version_id = await _harvested(harness, admin)

    assert await harness.service.list_relations(admin, version_id) == ()


async def test_low_cardinality_caps_confidence_and_says_so(
    harness: Harness, admin
) -> None:
    """A joinable type with few distinct values is still nearly no evidence."""
    harness.connector.tables = {
        "orders": descriptors(["status_code"], "String"),
        "shipments": descriptors(["status_code"], "String"),
    }
    harness.connector.overlaps = {
        ("orders.status_code", "shipments.status_code"): OverlapMeasurement(
            left_distinct=6,
            right_distinct=6,
            matched_distinct=6,
            sampled_rows=100_000,
        )
    }
    _, version_id = await _harvested(harness, admin)

    proposals = await harness.service.list_relations(admin, version_id)

    assert len(proposals) == 1
    assert proposals[0].binding_ceiling is BindingCeiling.CARDINALITY
    assert proposals[0].confidence <= 0.35


async def test_a_thin_sample_caps_confidence_and_says_so(
    harness: Harness, admin
) -> None:
    """Overlap over a handful of rows is a coincidence waiting to be believed."""
    harness.connector.tables = {
        "orders": descriptors(["customer_id"]),
        "customers": descriptors(["customer_id"]),
    }
    harness.connector.overlaps = {
        ("orders.customer_id", "customers.customer_id"): OverlapMeasurement(
            left_distinct=40,
            right_distinct=40,
            matched_distinct=40,
            sampled_rows=40,
        )
    }
    _, version_id = await _harvested(harness, admin)

    proposals = await harness.service.list_relations(admin, version_id)

    assert len(proposals) == 1
    assert proposals[0].binding_ceiling is BindingCeiling.SAMPLE_SIZE
    assert proposals[0].confidence <= 0.50


async def test_ample_evidence_leaves_confidence_unbound(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)

    proposal = (await harness.service.list_relations(admin, version_id))[0]

    assert proposal.binding_ceiling is BindingCeiling.NONE


async def test_mostly_non_matching_values_are_not_proposed(
    harness: Harness, admin
) -> None:
    """A pair whose values mostly differ is wrong, not weak."""
    harness.connector.tables = {
        "orders": descriptors(["customer_id"]),
        "customers": descriptors(["customer_id"]),
    }
    harness.connector.overlaps = {
        ("orders.customer_id", "customers.customer_id"): OverlapMeasurement(
            left_distinct=10_000,
            right_distinct=10_000,
            matched_distinct=1_000,
            sampled_rows=50_000,
        )
    }
    _, version_id = await _harvested(harness, admin)

    assert await harness.service.list_relations(admin, version_id) == ()


async def test_direction_is_stated_so_a_reviewer_knows_about_fan_out(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)

    proposal = (await harness.service.list_relations(admin, version_id))[0]

    assert proposal.cardinality.value in {"many_to_one", "one_to_many"}


async def test_proposals_are_ranked_by_confidence(harness: Harness, admin) -> None:
    harness.connector.tables = {
        "orders": descriptors(["customer_id", "region_code"]),
        "customers": descriptors(["customer_id", "region_code"]),
    }
    harness.connector.overlaps = {
        ("orders.customer_id", "customers.customer_id"): OverlapMeasurement(
            left_distinct=9000,
            right_distinct=9000,
            matched_distinct=9000,
            sampled_rows=90_000,
        ),
        ("orders.region_code", "customers.region_code"): OverlapMeasurement(
            left_distinct=50,
            right_distinct=50,
            matched_distinct=50,
            sampled_rows=90_000,
        ),
    }
    _, version_id = await _harvested(harness, admin)

    proposals = await harness.service.list_relations(admin, version_id)

    assert len(proposals) == 2
    assert proposals[0].confidence >= proposals[1].confidence


# ------------------------------------------------------------------ decisions


async def test_only_a_confirmed_relation_enters_the_join_graph(
    harness: Harness, admin
) -> None:
    """The safety property the whole design turns on."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    before = await harness.service.join_graph(admin, version_id)
    assert before.is_empty

    await harness.service.confirm_relation(admin, proposal.relation_id)
    after = await harness.service.join_graph(admin, version_id)

    assert len(after.relations) == 1


async def test_an_agent_may_not_join_on_an_unconfirmed_relation(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    permitted = await harness.service.permits_join(
        admin,
        catalog_version_id=version_id,
        left_field_id=proposal.left_field_id,
        right_field_id=proposal.right_field_id,
    )

    assert permitted is False


async def test_an_agent_may_join_once_a_human_confirmed(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    permitted = await harness.service.permits_join(
        admin,
        catalog_version_id=version_id,
        left_field_id=proposal.left_field_id,
        right_field_id=proposal.right_field_id,
    )

    assert permitted is True


async def test_join_permission_is_order_insensitive(harness: Harness, admin) -> None:
    """An agent writing the join the other way round writes the same join."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    permitted = await harness.service.permits_join(
        admin,
        catalog_version_id=version_id,
        left_field_id=proposal.right_field_id,
        right_field_id=proposal.left_field_id,
    )

    assert permitted is True


async def test_rejection_requires_and_records_a_reason(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    rejected = await harness.service.reject_relation(
        admin, proposal.relation_id, reason=RejectionReason.COINCIDENTAL_OVERLAP
    )

    assert rejected.state is RelationState.REJECTED
    assert rejected.rejection_reason is RejectionReason.COINCIDENTAL_OVERLAP


async def test_repeating_an_identical_decision_is_idempotent(
    harness: Harness, admin
) -> None:
    """A double-clicked button must not corrupt state."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    first = await harness.service.confirm_relation(admin, proposal.relation_id)
    second = await harness.service.confirm_relation(admin, proposal.relation_id)

    assert first.state is second.state is RelationState.CONFIRMED
    assert first.decided_at == second.decided_at


async def test_a_contradictory_decision_is_refused(harness: Harness, admin) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.reject_relation(
        admin, proposal.relation_id, reason=RejectionReason.NOT_A_REAL_RELATION
    )

    with pytest.raises(ConflictError):
        await harness.service.confirm_relation(admin, proposal.relation_id)


async def test_rejecting_twice_for_different_reasons_is_a_conflict(
    harness: Harness, admin
) -> None:
    """The recorded reason drives suppression; rewriting it silently would not."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.reject_relation(
        admin, proposal.relation_id, reason=RejectionReason.NOT_A_REAL_RELATION
    )

    with pytest.raises(ConflictError):
        await harness.service.reject_relation(
            admin, proposal.relation_id, reason=RejectionReason.WRONG_DIRECTION
        )


async def test_revoking_a_confirmation_removes_it_from_the_join_graph(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    await harness.service.revoke_relation(admin, proposal.relation_id)

    graph = await harness.service.join_graph(admin, version_id)
    assert graph.is_empty


async def test_revoking_an_unconfirmed_relation_is_a_conflict(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    with pytest.raises(ConflictError):
        await harness.service.revoke_relation(admin, proposal.relation_id)


async def test_a_viewer_cannot_confirm_a_relation(
    harness: Harness, admin, viewer
) -> None:
    """Confirming licenses agents to join; that is governance, not browsing."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    with pytest.raises(PermissionDeniedError):
        await harness.service.confirm_relation(viewer, proposal.relation_id)


async def test_a_member_cannot_confirm_a_relation(
    harness: Harness, admin, member
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    with pytest.raises(PermissionDeniedError):
        await harness.service.confirm_relation(member, proposal.relation_id)


async def test_relations_of_other_tenants_are_invisible(
    harness: Harness, admin, intruder
) -> None:
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]

    assert await harness.service.list_relations(intruder, version_id) == ()
    with pytest.raises(RelationNotFoundError):
        await harness.service.confirm_relation(intruder, proposal.relation_id)


# ------------------------------------------------------------------- declared


async def test_a_declared_relation_is_validated_against_real_data(
    harness: Harness, admin
) -> None:
    """The reviewer's typo can produce a wrong Finding as easily as ours."""
    harness.connector.tables = {
        "orders": descriptors(["a_code"]),
        "customers": descriptors(["z_code"]),
    }
    source, version_id = await _harvested(harness, admin)
    catalog = await harness.service.get_catalog(admin, version_id)
    left = catalog.tables[0].fields[0]
    right = catalog.tables[1].fields[0]

    with pytest.raises(ConflictError):
        await harness.service.declare_relation(
            admin,
            catalog_version_id=version_id,
            left_field_id=left.field_id,
            right_field_id=right.field_id,
        )


async def test_a_valid_declared_relation_enters_the_join_graph(
    harness: Harness, admin
) -> None:
    harness.connector.tables = {
        "orders": descriptors(["a_code"]),
        "customers": descriptors(["z_code"]),
    }
    harness.connector.overlaps = {
        ("orders.a_code", "customers.z_code"): OverlapMeasurement(
            left_distinct=8000,
            right_distinct=8000,
            matched_distinct=8000,
            sampled_rows=80_000,
        )
    }
    _, version_id = await _harvested(harness, admin)
    catalog = await harness.service.get_catalog(admin, version_id)
    left = catalog.tables[0].fields[0]
    right = catalog.tables[1].fields[0]

    declared = await harness.service.declare_relation(
        admin,
        catalog_version_id=version_id,
        left_field_id=left.field_id,
        right_field_id=right.field_id,
    )

    assert declared.origin is RelationOrigin.DECLARED
    assert declared.state is RelationState.CONFIRMED
    graph = await harness.service.join_graph(admin, version_id)
    assert len(graph.relations) == 1


async def test_isolated_fields_are_surfaced(harness: Harness, admin) -> None:
    """"Half your data is unreachable" is something a reviewer must be told."""
    load_tpch_subset(harness.connector)
    _, version_id = await _harvested(harness, admin)
    proposal = (await harness.service.list_relations(admin, version_id))[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    graph = await harness.service.join_graph(admin, version_id)

    assert "customer.c_name" in graph.isolated_fields
    assert "orders.o_custkey" not in graph.isolated_fields
