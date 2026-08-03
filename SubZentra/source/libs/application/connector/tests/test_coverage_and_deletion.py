"""Telling a reviewer what was *not* looked at, and what deletion would cost.

Both behaviours here exist for the same reason: a number that is absent reads as
a number that is zero. An empty proposal list looks like "your data has no
relationships" when it may mean "almost nothing here was eligible to be
examined", and a delete button looks free until it takes an afternoon of
confirmations with it.
"""

from __future__ import annotations

import pytest
from zentra_domain_connector import (
    COMPOSITE_KEY_LIMITATION,
    OverlapMeasurement,
    SourceKind,
    UploadFormat,
)

from zentra_application_connector import DataSourceNotFoundError

from .conftest import CREDENTIALS, Harness, descriptors, load_tpch_subset


async def _harvested(harness: Harness, actor):
    source = await harness.service.register_source(
        actor, name="Warehouse", credentials=CREDENTIALS
    )
    started = await harness.service.start_harvest(actor, source.data_source_id)
    status = await harness.service.run_harvest(actor, started.harvest_run_id)
    assert status.catalog_version_id is not None
    return source, status


# ------------------------------------------------------------------ coverage


async def test_skipped_fields_are_counted_rather_than_discarded(
    harness: Harness, admin
) -> None:
    """TPC-H's subset has fields no join could ever use — say how many."""
    load_tpch_subset(harness.connector)

    _, status = await _harvested(harness, admin)

    assert status.fields_unexamined > 0
    assert sum(status.unexamined_reasons.values()) == status.fields_unexamined


async def test_skipped_fields_are_grouped_by_why(harness: Harness, admin) -> None:
    """A list of column names communicates less than a reason and a count."""
    harness.connector.tables = {
        "orders": [
            *descriptors(["total"], "Float64"),
            *descriptors(["placed_at"], "DateTime"),
            *descriptors(["is_paid"], "Bool"),
        ],
    }

    _, status = await _harvested(harness, admin)

    reasons = " ".join(status.unexamined_reasons)
    assert "float" in reasons
    assert "temporal" in reasons
    assert "boolean" in reasons


async def test_a_harvest_states_what_inference_does_not_look_for(
    harness: Harness, admin
) -> None:
    """The composite-key limitation, on every run rather than only failures."""
    load_tpch_subset(harness.connector)

    _, status = await _harvested(harness, admin)

    assert COMPOSITE_KEY_LIMITATION in status.limitations


async def test_an_empty_join_graph_says_what_was_not_looked_for(
    harness: Harness, admin
) -> None:
    """The one moment emptiness is ambiguous is the moment to explain it."""
    load_tpch_subset(harness.connector)
    _, status = await _harvested(harness, admin)
    assert status.catalog_version_id is not None

    graph = await harness.service.join_graph(admin, status.catalog_version_id)

    assert graph.is_empty
    assert COMPOSITE_KEY_LIMITATION in graph.limitations


async def test_a_populated_join_graph_does_not_repeat_the_limitation(
    harness: Harness, admin
) -> None:
    """A caveat shown on every healthy response is a caveat nobody reads."""
    load_tpch_subset(harness.connector)
    _, status = await _harvested(harness, admin)
    assert status.catalog_version_id is not None
    proposals = await harness.service.list_relations(
        admin, status.catalog_version_id
    )
    proposal = proposals[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    graph = await harness.service.join_graph(admin, status.catalog_version_id)

    assert not graph.is_empty
    assert graph.limitations == ()


# ------------------------------------------------------------------ deletion


async def test_a_preview_reports_what_deletion_would_destroy(
    harness: Harness, admin
) -> None:
    load_tpch_subset(harness.connector)
    source, status = await _harvested(harness, admin)
    assert status.catalog_version_id is not None
    proposals = await harness.service.list_relations(
        admin, status.catalog_version_id
    )
    proposal = proposals[0]
    await harness.service.confirm_relation(admin, proposal.relation_id)

    preview = await harness.service.preview_source_deletion(
        admin, source.data_source_id
    )

    assert preview.name == "Warehouse"
    assert preview.catalog_versions == 1
    assert preview.confirmed_relations == 1


async def test_a_preview_counts_only_confirmed_relations(
    harness: Harness, admin
) -> None:
    """A proposal nobody acted on is not work deletion would destroy."""
    load_tpch_subset(harness.connector)
    source, _ = await _harvested(harness, admin)

    preview = await harness.service.preview_source_deletion(
        admin, source.data_source_id
    )

    assert preview.confirmed_relations == 0


async def test_a_preview_calls_out_cross_source_damage(
    harness: Harness, admin
) -> None:
    """Deleting one source silently degrading another is the surprise."""
    load_tpch_subset(harness.connector)
    warehouse, first = await _harvested(harness, admin)

    harness.landing.columns = descriptors(["c_custkey"])
    upload_preview = await harness.service.preview_upload(
        admin,
        filename="segments.csv",
        upload_format=UploadFormat.CSV,
        stream=_one(b"x"),
    )
    upload = await harness.service.commit_upload(
        admin, upload_preview.upload_id, name="Segments"
    )
    landed = harness.landing.landed[0].table
    harness.connector.tables[landed] = descriptors(["c_custkey"])
    harness.connector.table_meta = {
        **harness.connector.table_meta,
        landed: type(harness.connector.table_meta["customer"])(
            name=landed, database="zentra_uploads", estimated_rows=120_000
        ),
    }
    harness.connector.overlaps[(f"{landed}.c_custkey", "customer.c_custkey")] = (
        OverlapMeasurement(
            left_distinct=120_000,
            right_distinct=150_000,
            matched_distinct=120_000,
            sampled_rows=120_000,
            right_is_unique=True,
        )
    )
    run = await harness.service.start_harvest(admin, upload.data_source_id)
    status = await harness.service.run_harvest(admin, run.harvest_run_id)
    assert status.catalog_version_id is not None
    cross = [
        r
        for r in await harness.service.list_relations(admin, status.catalog_version_id)
        if r.is_cross_source
    ]
    await harness.service.confirm_relation(admin, cross[0].relation_id)

    preview = await harness.service.preview_source_deletion(
        admin, warehouse.data_source_id
    )

    assert preview.cross_source_relations == 1


async def test_a_preview_flags_an_upload_whose_data_is_dropped(
    harness: Harness, admin
) -> None:
    """A connected source loses metadata; an uploaded one loses the rows."""
    harness.landing.columns = descriptors(["customer_id"])
    upload_preview = await harness.service.preview_upload(
        admin, filename="c.csv", upload_format=UploadFormat.CSV, stream=_one(b"x")
    )
    upload = await harness.service.commit_upload(
        admin, upload_preview.upload_id, name="Extract"
    )

    preview = await harness.service.preview_source_deletion(
        admin, upload.data_source_id
    )

    assert preview.drops_stored_data is True


async def test_a_connected_source_preview_does_not_claim_to_drop_data(
    harness: Harness, admin
) -> None:
    source = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    preview = await harness.service.preview_source_deletion(
        admin, source.data_source_id
    )

    assert preview.drops_stored_data is False
    assert SourceKind.CONNECTED is SourceKind("connected")


async def test_a_preview_of_another_tenants_source_is_not_found(
    harness: Harness, admin, intruder
) -> None:
    source = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    with pytest.raises(DataSourceNotFoundError):
        await harness.service.preview_source_deletion(
            intruder, source.data_source_id
        )


async def _one(payload: bytes):
    yield payload
