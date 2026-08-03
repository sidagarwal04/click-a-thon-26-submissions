"""`CatalogResponse.from_version` folding in agent-access overrides.

The route tests in `test_connector_api.py` cover the PATCH endpoints
themselves; this covers the merge this response builds on the way out of
`GET /sources/{id}/catalog` and `GET /catalog-versions/{id}`, which needs a
working catalog repository to exercise end to end and so is cheaper to assert
directly against the response schema.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from zentra_domain_connector import (
    AccessOverrides,
    CatalogAccessOverride,
    CatalogVersion,
    FieldProfile,
    SourceField,
    SourceTable,
    TypeFamily,
)

from zentra_api.connector_schemas import CatalogResponse

DATA_SOURCE_ID = uuid4()
TENANT_ID = uuid4()


def _version() -> CatalogVersion:
    table_id = uuid4()
    return CatalogVersion(
        catalog_version_id=uuid4(),
        data_source_id=DATA_SOURCE_ID,
        tenant_id=TENANT_ID,
        harvest_run_id=uuid4(),
        created_at=datetime.now(UTC),
        tables=(
            SourceTable(
                table_id=table_id,
                name="customers",
                database="db",
                fields=(
                    SourceField(
                        field_id=uuid4(),
                        table_id=table_id,
                        name="email",
                        declared_type="String",
                        family=TypeFamily.STRING,
                        normalised_type="string",
                        nullable=True,
                        position=0,
                        profile=FieldProfile(sampled_rows=10),
                    ),
                    SourceField(
                        field_id=uuid4(),
                        table_id=table_id,
                        name="id",
                        declared_type="Int64",
                        family=TypeFamily.INTEGER,
                        normalised_type="int64",
                        nullable=False,
                        position=1,
                    ),
                ),
            ),
        ),
    )


def test_every_table_and_field_defaults_to_agent_visible() -> None:
    response = CatalogResponse.from_version(_version())

    table = response.tables[0]
    assert table.agent_visible is True
    assert all(field.agent_visible for field in table.fields)


def test_a_field_override_reports_false_without_hiding_its_siblings() -> None:
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            CatalogAccessOverride(
                override_id=uuid4(),
                tenant_id=TENANT_ID,
                data_source_id=DATA_SOURCE_ID,
                table_name="customers",
                field_name="email",
                agent_visible=False,
                decided_by=uuid4(),
                decided_at=datetime.now(UTC),
            ),
        ),
    )

    response = CatalogResponse.from_version(_version(), overrides=overrides)

    table = response.tables[0]
    assert table.agent_visible is True
    by_name = {f.name: f.agent_visible for f in table.fields}
    assert by_name == {"email": False, "id": True}


def test_a_table_override_reports_false_for_the_whole_table() -> None:
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            CatalogAccessOverride(
                override_id=uuid4(),
                tenant_id=TENANT_ID,
                data_source_id=DATA_SOURCE_ID,
                table_name="customers",
                field_name=None,
                agent_visible=False,
                decided_by=uuid4(),
                decided_at=datetime.now(UTC),
            ),
        ),
    )

    response = CatalogResponse.from_version(_version(), overrides=overrides)

    assert response.tables[0].agent_visible is False
