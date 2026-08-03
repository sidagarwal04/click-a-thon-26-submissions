from uuid import UUID

from zentra_domain_agent_execution import (
    SemanticCatalog,
    SemanticDimension,
    SemanticMeasure,
)

from zentra_domain_investigation import AnalyticalScope

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")

CATALOG = SemanticCatalog(
    measures=(
        SemanticMeasure(name="Commerce.refundAmount", type="sum"),
        SemanticMeasure(name="Channel.revenue", type="sum"),
    ),
    dimensions=(
        SemanticDimension(name="Commerce.orderedAt", type="time"),
        SemanticDimension(name="Channel.region", type="string"),
    ),
)


def test_unrestricted_scope_returns_the_full_catalog() -> None:
    scope = AnalyticalScope.unrestricted(TENANT_ID)

    assert scope.is_unrestricted is True
    assert scope.narrow(CATALOG) == CATALOG


def test_scope_narrows_to_only_the_allowed_cube() -> None:
    scope = AnalyticalScope(tenant_id=TENANT_ID, cubes=frozenset({"Commerce"}))

    narrowed = scope.narrow(CATALOG)

    assert narrowed.member_names() == frozenset(
        {"Commerce.refundAmount", "Commerce.orderedAt"}
    )


def test_member_override_grants_one_member_from_an_out_of_scope_cube() -> None:
    scope = AnalyticalScope(
        tenant_id=TENANT_ID,
        cubes=frozenset({"Commerce"}),
        member_overrides=frozenset({"Channel.revenue"}),
    )

    narrowed = scope.narrow(CATALOG)

    assert narrowed.member_names() == frozenset(
        {"Commerce.refundAmount", "Commerce.orderedAt", "Channel.revenue"}
    )


def test_scope_never_widens_past_the_source_catalog() -> None:
    scope = AnalyticalScope(
        tenant_id=TENANT_ID,
        cubes=frozenset({"Commerce", "DoesNotExist"}),
        member_overrides=frozenset({"Nonexistent.member"}),
    )

    narrowed = scope.narrow(CATALOG)

    assert narrowed.member_names() <= CATALOG.member_names()
