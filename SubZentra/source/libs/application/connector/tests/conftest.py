"""Fixtures for the ConnectorService seam.

Fixed UUID constants rather than generated ones, mirroring
``libs/application/investigation/tests/test_service.py`` — a failure that names
a stable id is one you can reason about.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

import pytest
from zentra_domain_connector import FieldProfile, OverlapMeasurement

from zentra_application_connector import (
    AuthenticatedActor,
    ConnectorService,
    Role,
    SourceCredentials,
    SourceFieldDescriptor,
    SourceTableDescriptor,
)

from .fakes import (
    FakeAgentAccessRepository,
    FakeCatalogRepository,
    FakeCipher,
    FakeClock,
    FakeConnector,
    FakeHarvestRunRepository,
    FakeLandingZone,
    FakeRelationRepository,
    FakeSourceRepository,
)

TENANT_ID = UUID("61000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = UUID("61000000-0000-0000-0000-0000000000ff")
USER_ID = UUID("62000000-0000-0000-0000-000000000002")

CREDENTIALS = SourceCredentials(
    host="warehouse.example",
    port=8443,
    database="tpch",
    username="reader",
    password="s3cret-do-not-leak",
)


@dataclass
class Harness:
    service: ConnectorService
    connector: FakeConnector
    cipher: FakeCipher
    landing: FakeLandingZone
    sources: FakeSourceRepository
    catalogs: FakeCatalogRepository
    relations: FakeRelationRepository
    runs: FakeHarvestRunRepository
    access: FakeAgentAccessRepository


@pytest.fixture
def admin() -> AuthenticatedActor:
    return AuthenticatedActor(user_id=USER_ID, tenant_id=TENANT_ID, role=Role.ADMIN)


@pytest.fixture
def member() -> AuthenticatedActor:
    return AuthenticatedActor(user_id=USER_ID, tenant_id=TENANT_ID, role=Role.MEMBER)


@pytest.fixture
def viewer() -> AuthenticatedActor:
    return AuthenticatedActor(user_id=USER_ID, tenant_id=TENANT_ID, role=Role.VIEWER)


@pytest.fixture
def intruder() -> AuthenticatedActor:
    """An admin of a different Tenant, used to prove isolation."""
    return AuthenticatedActor(
        user_id=USER_ID, tenant_id=OTHER_TENANT_ID, role=Role.ADMIN
    )


@pytest.fixture
def harness() -> Harness:
    connector = FakeConnector()
    cipher = FakeCipher()
    landing = FakeLandingZone()
    sources = FakeSourceRepository()
    catalogs = FakeCatalogRepository()
    relations = FakeRelationRepository()
    runs = FakeHarvestRunRepository()
    access = FakeAgentAccessRepository()
    service = ConnectorService(
        sources=sources,
        catalogs=catalogs,
        relations=relations,
        runs=runs,
        access=access,
        connector=connector,
        cipher=cipher,
        landing_zone=landing,
        clock=FakeClock(),
    )
    return Harness(
        service=service,
        connector=connector,
        cipher=cipher,
        landing=landing,
        sources=sources,
        catalogs=catalogs,
        relations=relations,
        runs=runs,
        access=access,
    )


def field_descriptor(
    name: str, declared_type: str = "Int64", position: int = 0
) -> SourceFieldDescriptor:
    return SourceFieldDescriptor(
        name=name, declared_type=declared_type, nullable=False, position=position
    )


def load_tpch_subset(connector: FakeConnector) -> None:
    """Two TPC-H tables with one real foreign key between them.

    ``orders.o_custkey`` references ``customer.c_custkey``. Row and distinct
    counts follow TPC-H at scale factor 1 rather than being made small for
    convenience: the cardinality ceiling is sensitive to how many distinct
    values a key really has, so a shrunken fixture would exercise a bound the
    real dataset never hits.
    """
    connector.tables = {
        "customer": [
            field_descriptor("c_custkey", "Int64", 0),
            field_descriptor("c_name", "String", 1),
            field_descriptor("c_nationkey", "Int64", 2),
        ],
        "orders": [
            field_descriptor("o_orderkey", "Int64", 0),
            field_descriptor("o_custkey", "Int64", 1),
            field_descriptor("o_totalprice", "Decimal(12,2)", 2),
        ],
    }
    connector.table_meta = {
        "customer": SourceTableDescriptor(
            name="customer", database="tpch", estimated_rows=150_000
        ),
        "orders": SourceTableDescriptor(
            name="orders", database="tpch", estimated_rows=1_500_000
        ),
    }
    connector.profiles = {
        "customer.c_custkey": FieldProfile(
            sampled_rows=150_000, distinct_count=150_000, null_fraction=0.0
        ),
        "orders.o_custkey": FieldProfile(
            sampled_rows=1_500_000, distinct_count=99_996, null_fraction=0.0
        ),
    }
    connector.overlaps = {
        ("orders.o_custkey", "customer.c_custkey"): OverlapMeasurement(
            left_distinct=99_996,
            right_distinct=150_000,
            matched_distinct=99_996,
            sampled_rows=1_500_000,
            right_is_unique=True,
        )
    }


def descriptors(names: Sequence[str], declared_type: str = "Int64"):
    return [field_descriptor(n, declared_type, i) for i, n in enumerate(names)]
