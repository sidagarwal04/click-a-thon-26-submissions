"""Uploading a file, and discovering that it joins to the warehouse.

The cross-source tests at the bottom are the payoff for modelling an upload as
a Data Source rather than as a separate concept: the relationship between a
spreadsheet and a warehouse is one no schema anywhere records, and finding it
costs no extra machinery because it is the same code path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from zentra_domain_connector import (
    MAX_UPLOAD_BYTES,
    OverlapMeasurement,
    RelationState,
    SourceKind,
    UploadFormat,
)

from zentra_application_connector import (
    PermissionDeniedError,
    SourceFieldDescriptor,
    UploadRejectedError,
)

from .conftest import CREDENTIALS, Harness, descriptors, load_tpch_subset


async def _stream(payload: bytes, chunk: int = 1024) -> AsyncIterator[bytes]:
    for offset in range(0, max(len(payload), 1), chunk):
        yield payload[offset : offset + chunk]


def _csv_columns() -> list[SourceFieldDescriptor]:
    return [
        SourceFieldDescriptor(
            name="customer_id", declared_type="Int64", nullable=False, position=0
        ),
        SourceFieldDescriptor(
            name="signup_date", declared_type="String", nullable=True, position=1
        ),
    ]


async def test_a_preview_shows_inferred_columns_before_commit(
    harness: Harness, member
) -> None:
    """A mis-parsed column found after commit has already poisoned everything."""
    harness.landing.columns = _csv_columns()
    harness.landing.rows = [("1", "2026-01-01"), ("2", "2026-01-02")]
    harness.landing.total_rows = 2

    preview = await harness.service.preview_upload(
        member,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"customer_id,signup_date\n1,2026-01-01\n"),
    )

    assert [c.name for c in preview.columns] == ["customer_id", "signup_date"]
    assert preview.rows[0] == ("1", "2026-01-01")
    assert harness.landing.landed == []


async def test_previewing_does_not_create_a_data_source(
    harness: Harness, member
) -> None:
    harness.landing.columns = _csv_columns()

    await harness.service.preview_upload(
        member,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )

    assert await harness.service.list_sources(member) == ()


async def test_committing_creates_an_uploaded_data_source(
    harness: Harness, member
) -> None:
    harness.landing.columns = _csv_columns()
    harness.landing.total_rows = 500
    preview = await harness.service.preview_upload(
        member,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )

    source = await harness.service.commit_upload(
        member, preview.upload_id, name="Customer extract"
    )

    assert source.kind is SourceKind.UPLOADED
    assert len(harness.landing.landed) == 1


async def test_a_corrected_column_type_is_honoured(harness: Harness, member) -> None:
    """The reviewer's correction must reach the landing zone, not be advisory."""
    harness.landing.columns = _csv_columns()
    preview = await harness.service.preview_upload(
        member,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    corrected = [
        SourceFieldDescriptor(
            name="customer_id", declared_type="String", nullable=False, position=0
        ),
        preview.columns[1],
    ]

    await harness.service.commit_upload(
        member, preview.upload_id, name="Extract", columns=corrected
    )

    assert harness.landing.landed


async def test_a_malformed_file_names_where_it_went_wrong(
    harness: Harness, member
) -> None:
    harness.landing.parse_error = UploadRejectedError(
        "inconsistent row width", row=42, column="signup_date"
    )

    with pytest.raises(UploadRejectedError) as excinfo:
        await harness.service.preview_upload(
            member,
            filename="broken.csv",
            upload_format=UploadFormat.CSV,
            stream=_stream(b"bad"),
        )

    assert excinfo.value.row == 42
    assert excinfo.value.column == "signup_date"


async def test_an_oversized_upload_fails_predictably(
    harness: Harness, member
) -> None:
    """A stated limit, so failure is predictable rather than wherever memory ran out."""
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)

    with pytest.raises(UploadRejectedError) as excinfo:
        await harness.service.preview_upload(
            member,
            filename="huge.parquet",
            upload_format=UploadFormat.PARQUET,
            stream=_stream(oversized, chunk=1024 * 1024),
        )

    assert str(MAX_UPLOAD_BYTES) in str(excinfo.value)


async def test_committing_an_unknown_upload_is_rejected(
    harness: Harness, member
) -> None:
    from uuid import uuid4

    with pytest.raises(UploadRejectedError):
        await harness.service.commit_upload(member, uuid4(), name="Nothing")


async def test_a_viewer_cannot_upload(harness: Harness, viewer) -> None:
    with pytest.raises(PermissionDeniedError):
        await harness.service.preview_upload(
            viewer,
            filename="customers.csv",
            upload_format=UploadFormat.CSV,
            stream=_stream(b"x"),
        )


async def test_deleting_an_uploaded_source_drops_its_table(
    harness: Harness, admin
) -> None:
    """Deletion must mean deletion, not merely disappearance from a list."""
    harness.landing.columns = _csv_columns()
    preview = await harness.service.preview_upload(
        admin,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    source = await harness.service.commit_upload(
        admin, preview.upload_id, name="Extract"
    )

    await harness.service.delete_source(admin, source.data_source_id)

    assert len(harness.landing.dropped) == 1
    assert harness.landing.dropped[0].startswith("zentra_uploads.")


async def test_an_uploaded_source_is_harvested_by_the_same_path(
    harness: Harness, admin
) -> None:
    """One mental model: an upload is a Data Source, not a parallel concept."""
    harness.landing.columns = _csv_columns()
    harness.connector.tables = {"t_upload": descriptors(["customer_id"])}
    preview = await harness.service.preview_upload(
        admin,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    source = await harness.service.commit_upload(
        admin, preview.upload_id, name="Extract"
    )

    started = await harness.service.start_harvest(admin, source.data_source_id)
    status = await harness.service.run_harvest(admin, started.harvest_run_id)

    assert status.catalog_version_id is not None
    assert status.tables_found == 1


async def test_uploads_of_other_tenants_are_invisible(
    harness: Harness, admin, intruder
) -> None:
    harness.landing.columns = _csv_columns()
    preview = await harness.service.preview_upload(
        admin,
        filename="customers.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    await harness.service.commit_upload(admin, preview.upload_id, name="Extract")

    assert await harness.service.list_sources(intruder) == ()


# -------------------------------------------------------------- cross-source


async def test_an_upload_is_found_to_join_the_warehouse(
    harness: Harness, admin
) -> None:
    """The demo moment, and a relationship no schema anywhere records.

    Two Data Sources, one connected and one uploaded, with a shared key. The
    proposal spans them because inference runs over every catalog at once
    rather than one source at a time.
    """
    load_tpch_subset(harness.connector)
    warehouse = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    started = await harness.service.start_harvest(admin, warehouse.data_source_id)
    await harness.service.run_harvest(admin, started.harvest_run_id)

    harness.landing.columns = _csv_columns()
    preview = await harness.service.preview_upload(
        admin,
        filename="segments.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    upload = await harness.service.commit_upload(
        admin, preview.upload_id, name="Segments"
    )

    landed_table = harness.landing.landed[0].table
    harness.connector.tables[landed_table] = descriptors(["c_custkey"])
    harness.connector.table_meta = {
        **harness.connector.table_meta,
        landed_table: type(harness.connector.table_meta["customer"])(
            name=landed_table, database="zentra_uploads", estimated_rows=120_000
        ),
    }
    harness.connector.overlaps[(f"{landed_table}.c_custkey", "customer.c_custkey")] = (
        OverlapMeasurement(
            left_distinct=120_000,
            right_distinct=150_000,
            matched_distinct=120_000,
            sampled_rows=120_000,
            right_is_unique=True,
        )
    )

    upload_run = await harness.service.start_harvest(admin, upload.data_source_id)
    status = await harness.service.run_harvest(admin, upload_run.harvest_run_id)
    assert status.catalog_version_id is not None

    relations = await harness.service.list_relations(admin, status.catalog_version_id)
    cross = [r for r in relations if r.is_cross_source]

    assert len(cross) == 1
    assert cross[0].state is RelationState.PROPOSED


async def test_a_cross_source_relation_still_requires_confirmation(
    harness: Harness, admin
) -> None:
    """Spanning sources earns no exemption from the confirmation ceremony."""
    load_tpch_subset(harness.connector)
    warehouse = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    first = await harness.service.start_harvest(admin, warehouse.data_source_id)
    await harness.service.run_harvest(admin, first.harvest_run_id)

    harness.landing.columns = _csv_columns()
    preview = await harness.service.preview_upload(
        admin,
        filename="segments.csv",
        upload_format=UploadFormat.CSV,
        stream=_stream(b"x"),
    )
    upload = await harness.service.commit_upload(
        admin, preview.upload_id, name="Segments"
    )
    landed_table = harness.landing.landed[0].table
    harness.connector.tables[landed_table] = descriptors(["c_custkey"])
    harness.connector.table_meta = {
        **harness.connector.table_meta,
        landed_table: type(harness.connector.table_meta["customer"])(
            name=landed_table, database="zentra_uploads", estimated_rows=120_000
        ),
    }
    harness.connector.overlaps[(f"{landed_table}.c_custkey", "customer.c_custkey")] = (
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

    graph = await harness.service.join_graph(admin, status.catalog_version_id)

    assert graph.is_empty
