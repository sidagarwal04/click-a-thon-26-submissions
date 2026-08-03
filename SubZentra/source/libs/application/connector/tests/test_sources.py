"""Registering Data Sources, and keeping their credentials out of sight."""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import pytest
from zentra_domain_connector import ConnectionFailure, SourceHealth, SourceKind

from zentra_application_connector import (
    ConflictError,
    ConnectionFailedError,
    DataSourceNotFoundError,
    PermissionDeniedError,
)

from .conftest import CREDENTIALS, Harness


async def test_registering_a_reachable_source_persists_it(
    harness: Harness, admin
) -> None:
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    assert summary.name == "Warehouse"
    assert summary.kind is SourceKind.CONNECTED
    assert summary.health is SourceHealth.REACHABLE
    assert summary.last_verified_at is not None
    assert len(harness.sources.items) == 1


async def test_registration_verifies_before_persisting_anything(
    harness: Harness, admin
) -> None:
    """An unreachable source must not be saved at all.

    Persisting first and verifying after would leave a broken source in the
    list for everyone else, and leave the admin unsure whether they mistyped a
    password or hit a firewall.
    """
    harness.connector.reachable = False
    harness.connector.failure = ConnectionFailure.UNREACHABLE

    with pytest.raises(ConnectionFailedError) as excinfo:
        await harness.service.register_source(
            admin, name="Warehouse", credentials=CREDENTIALS
        )

    assert excinfo.value.failure is ConnectionFailure.UNREACHABLE
    assert harness.sources.items == {}


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionFailure.UNREACHABLE,
        ConnectionFailure.AUTHENTICATION_FAILED,
        ConnectionFailure.DATABASE_NOT_FOUND,
    ],
)
async def test_the_three_failure_kinds_are_distinguishable(
    harness: Harness, admin, failure
) -> None:
    """Each failure tells the admin which field to fix."""
    harness.connector.reachable = False
    harness.connector.failure = failure

    with pytest.raises(ConnectionFailedError) as excinfo:
        await harness.service.register_source(
            admin, name="Warehouse", credentials=CREDENTIALS
        )

    assert excinfo.value.failure is failure


async def test_credentials_are_sealed_before_storage(harness: Harness, admin) -> None:
    await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    stored = next(iter(harness.sources.items.values()))
    assert stored.sealed_credentials is not None
    assert CREDENTIALS.password.encode() not in stored.sealed_credentials


async def test_no_read_model_can_carry_a_credential(harness: Harness, admin) -> None:
    """The redaction is structural, not a matter of remembering to redact.

    Asserted over the whole serialised summary rather than field by field, so
    that adding a field to ``SourceSummary`` later cannot quietly reintroduce a
    leak.
    """
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    rendered = repr(dataclasses.asdict(summary))
    assert CREDENTIALS.password not in rendered
    assert CREDENTIALS.username not in rendered
    assert not hasattr(summary, "credentials")


async def test_connection_hint_identifies_without_exposing(
    harness: Harness, admin
) -> None:
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    assert summary.connection_hint == "warehouse.example/tpch"
    assert CREDENTIALS.username not in (summary.connection_hint or "")


async def test_rotating_credentials_preserves_source_identity(
    harness: Harness, admin
) -> None:
    """Rotation must not orphan the catalog or any confirmed Relation."""
    original = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    rotated = dataclasses.replace(CREDENTIALS, password="new-secret")

    updated = await harness.service.update_credentials(
        admin, original.data_source_id, credentials=rotated
    )

    assert updated.data_source_id == original.data_source_id
    assert harness.cipher.sealed[-1].password == "new-secret"


async def test_rotation_to_bad_credentials_is_refused(harness: Harness, admin) -> None:
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    harness.connector.reachable = False

    with pytest.raises(ConnectionFailedError):
        await harness.service.update_credentials(
            admin, summary.data_source_id, credentials=CREDENTIALS
        )

    stored = harness.sources.items[summary.data_source_id]
    assert stored.sealed_credentials == b"sealed::0"


async def test_failed_connection_test_records_unreachable_health(
    harness: Harness, admin
) -> None:
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )
    harness.connector.reachable = False

    with pytest.raises(ConnectionFailedError):
        await harness.service.test_connection(admin, summary.data_source_id)

    assert harness.sources.items[summary.data_source_id].health is (
        SourceHealth.UNREACHABLE
    )


async def test_sources_of_other_tenants_are_invisible(
    harness: Harness, admin, intruder
) -> None:
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    assert await harness.service.list_sources(intruder) == ()
    with pytest.raises(DataSourceNotFoundError):
        await harness.service.get_source(intruder, summary.data_source_id)


async def test_a_viewer_cannot_register_a_source(harness: Harness, viewer) -> None:
    with pytest.raises(PermissionDeniedError):
        await harness.service.register_source(
            viewer, name="Warehouse", credentials=CREDENTIALS
        )


async def test_a_viewer_may_read_sources(harness: Harness, admin, viewer) -> None:
    await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    assert len(await harness.service.list_sources(viewer)) == 1


async def test_deleting_an_unknown_source_is_reported(harness: Harness, admin) -> None:
    with pytest.raises(DataSourceNotFoundError):
        await harness.service.delete_source(admin, uuid4())


async def test_deleting_a_connected_source_drops_no_table(
    harness: Harness, admin
) -> None:
    """Only uploaded sources own storage. A connected one must not be touched."""
    summary = await harness.service.register_source(
        admin, name="Warehouse", credentials=CREDENTIALS
    )

    await harness.service.delete_source(admin, summary.data_source_id)

    assert harness.landing.dropped == []
    assert harness.sources.items == {}


async def test_conflict_is_not_raised_for_a_second_distinct_source(
    harness: Harness, admin
) -> None:
    await harness.service.register_source(admin, name="A", credentials=CREDENTIALS)
    await harness.service.register_source(admin, name="B", credentials=CREDENTIALS)

    assert len(await harness.service.list_sources(admin)) == 2


async def test_conflict_error_is_distinct_from_not_found(harness: Harness) -> None:
    """The two failure families must not be conflated by callers mapping to HTTP."""
    assert not issubclass(ConflictError, DataSourceNotFoundError)
    assert not issubclass(DataSourceNotFoundError, ConflictError)
