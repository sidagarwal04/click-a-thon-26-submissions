"""Harvesting: phases, budgets, partial failure, concurrency, cancellation."""

from __future__ import annotations

import pytest
from zentra_domain_connector import (
    FieldProfile,
    HarvestBudget,
    HarvestPhase,
    HarvestScope,
)

from zentra_application_connector import ConflictError, PermissionDeniedError

from .conftest import CREDENTIALS, Harness, descriptors, load_tpch_subset


async def _register(harness: Harness, actor):
    return await harness.service.register_source(
        actor, name="Warehouse", credentials=CREDENTIALS
    )


async def test_starting_a_harvest_returns_immediately_without_results(
    harness: Harness, admin
) -> None:
    """The point of 202 is that the caller is not made to wait."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)

    status = await harness.service.start_harvest(admin, source.data_source_id)

    assert status.phase is HarvestPhase.PENDING
    assert status.catalog_version_id is None
    assert harness.connector.describe_calls == 0


async def test_a_completed_harvest_produces_a_catalog_version(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.phase is HarvestPhase.COMPLETED
    assert status.catalog_version_id is not None
    assert status.tables_found == 2
    assert status.fields_described == 6


async def test_counts_advance_per_phase(harness: Harness, admin) -> None:
    """Counts rather than a percentage: a percentage of an unknown total lies."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.fields_profiled == 6
    assert status.queries_used > 0
    assert status.queries_budget == HarvestBudget().max_queries


async def test_catalog_is_readable_after_the_run(harness: Harness, admin) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    catalog = await harness.service.latest_catalog(admin, source.data_source_id)

    assert {t.name for t in catalog.tables} == {"customer", "orders"}
    customer = next(t for t in catalog.tables if t.name == "customer")
    assert customer.estimated_rows == 150_000
    assert [f.name for f in customer.fields] == ["c_custkey", "c_name", "c_nationkey"]


async def test_scope_restricts_which_tables_are_read(harness: Harness, admin) -> None:
    """A thousand-table warehouse should not be swept to profile eight."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(
        admin, source.data_source_id, scope=HarvestScope(tables=("orders",))
    )

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.tables_found == 1
    catalog = await harness.service.latest_catalog(admin, source.data_source_id)
    assert {t.name for t in catalog.tables} == {"orders"}


async def test_an_unreadable_table_does_not_discard_the_run(
    harness: Harness, admin
) -> None:
    """One permission-denied table is a gap, not a failure."""
    load_tpch_subset(harness.connector)
    harness.connector.unreadable_tables = {"customer"}
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.phase is HarvestPhase.COMPLETED
    assert status.unreadable_count == 1
    catalog = await harness.service.latest_catalog(admin, source.data_source_id)
    assert {t.name for t in catalog.tables} == {"orders"}


async def test_unreadable_tables_are_reported_with_their_reason(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    harness.connector.unreadable_tables = {"customer"}
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    status = await harness.service.get_harvest(admin, started.harvest_run_id)

    assert len(status.unreadable) == 1
    name, reason = status.unreadable[0]
    assert name == "tpch.customer"
    assert "permission denied" in reason


async def test_budget_exhaustion_stops_the_run_but_keeps_what_it_learned(
    harness: Harness, admin
) -> None:
    """A run that hits its ceiling must not throw away the work it paid for."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(
        admin, source.data_source_id, budget=HarvestBudget(max_queries=2)
    )

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.phase is HarvestPhase.COMPLETED
    assert status.queries_used <= 3
    assert status.fields_profiled == 0
    catalog = await harness.service.latest_catalog(admin, source.data_source_id)
    assert len(catalog.tables) >= 1


async def test_budget_consumption_is_reported(harness: Harness, admin) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(
        admin, source.data_source_id, budget=HarvestBudget(max_queries=50)
    )

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert 0 < status.queries_used <= 50
    assert status.queries_budget == 50


async def test_a_second_concurrent_harvest_is_refused(harness: Harness, admin) -> None:
    """Two runs interleaving would produce a catalog that never existed."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    await harness.service.start_harvest(admin, source.data_source_id)

    with pytest.raises(ConflictError):
        await harness.service.start_harvest(admin, source.data_source_id)


async def test_a_new_harvest_is_allowed_once_the_previous_finished(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    first = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, first.harvest_run_id)

    second = await harness.service.start_harvest(admin, source.data_source_id)

    assert second.harvest_run_id != first.harvest_run_id


async def test_cancellation_stops_the_run_at_its_next_checkpoint(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.cancel_harvest(admin, started.harvest_run_id)

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.phase is HarvestPhase.CANCELLED
    assert harness.connector.describe_calls == 0


async def test_cancelling_a_finished_run_is_a_conflict(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    with pytest.raises(ConflictError):
        await harness.service.cancel_harvest(admin, started.harvest_run_id)


async def test_a_run_that_dies_reaches_a_terminal_failed_state(
    harness: Harness, admin
) -> None:
    """A run stuck in `running` is indistinguishable from one that is slow."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)

    async def explode(*args, **kwargs):
        raise RuntimeError("connection reset by peer")

    harness.connector.list_tables = explode  # type: ignore[method-assign]

    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.phase is HarvestPhase.FAILED
    assert status.failure_code == "harvest_failed"
    assert status.finished_at is not None


async def test_harvest_history_is_listable(harness: Harness, admin) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    first = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, first.harvest_run_id)
    second = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, second.harvest_run_id)

    history = await harness.service.list_harvests(admin, source.data_source_id)

    assert len(history) == 2


async def test_a_viewer_cannot_start_a_harvest(
    harness: Harness, admin, viewer
) -> None:
    source = await _register(harness, admin)

    with pytest.raises(PermissionDeniedError):
        await harness.service.start_harvest(viewer, source.data_source_id)


async def test_a_member_may_start_a_harvest(harness: Harness, admin, member) -> None:
    """A harvest changes nothing a human decided; it refreshes an observation."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)

    status = await harness.service.start_harvest(member, source.data_source_id)

    assert status.phase is HarvestPhase.PENDING


async def test_sample_values_are_not_requested_by_default(
    harness: Harness, admin
) -> None:
    """Off by default, because retained values would be a new data posture."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    assert harness.connector.sample_values_requested
    assert not any(harness.connector.sample_values_requested)


async def test_sample_values_are_requested_only_when_opted_in(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source = await harness.service.register_source(
        admin, name="W", credentials=CREDENTIALS, store_sample_values=True
    )
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    assert all(harness.connector.sample_values_requested)


async def test_no_raw_value_is_persisted_when_opted_out(
    harness: Harness, admin
) -> None:
    """The default must cost nothing in functionality and everything in exposure."""
    load_tpch_subset(harness.connector)
    harness.connector.profiles["customer.c_name"] = FieldProfile(
        sampled_rows=1500,
        distinct_count=1400,
        sample_values=("Alice Smith", "Bob Jones"),
    )
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    catalog = await harness.service.latest_catalog(admin, source.data_source_id)
    values = [
        v
        for table in catalog.tables
        for f in table.fields
        if f.profile
        for v in f.profile.sample_values
    ]
    assert values == []


async def test_profiles_state_the_sample_they_were_observed_over(
    harness: Harness, admin
) -> None:
    """No statistic may be presented without the size of its evidence."""
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    catalog = await harness.service.latest_catalog(admin, source.data_source_id)
    profiles = [
        f.profile for table in catalog.tables for f in table.fields if f.profile
    ]
    assert profiles
    assert all(p.sampled_rows > 0 for p in profiles)


async def test_catalog_search_finds_a_field_across_tables(
    harness: Harness, admin
) -> None:
    harness.connector.tables = {
        "orders": descriptors(["customer_id", "total"]),
        "invoices": descriptors(["customer_id", "amount"]),
    }
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)
    status = await harness.service.run_harvest(admin, started.harvest_run_id)
    assert status.catalog_version_id is not None

    hits = await harness.service.search_catalog(
        admin, status.catalog_version_id, "customer_id"
    )

    assert set(hits) == {"orders.customer_id", "invoices.customer_id"}


async def test_harvests_of_other_tenants_are_invisible(
    harness: Harness, admin, intruder
) -> None:
    load_tpch_subset(harness.connector)
    source = await _register(harness, admin)
    started = await harness.service.start_harvest(admin, source.data_source_id)

    from zentra_application_connector import HarvestRunNotFoundError

    with pytest.raises(HarvestRunNotFoundError):
        await harness.service.get_harvest(intruder, started.harvest_run_id)
