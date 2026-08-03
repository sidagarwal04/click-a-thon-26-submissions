"""Toggling agent access to a table or field.

What matters here is external: who is allowed to change the toggle, that a
repeat toggle updates rather than accumulates, and that the default with no
override is visible. The catalog-filtering logic itself is asserted at the
domain layer (`AccessOverrides.apply`), not re-tested here.
"""

from __future__ import annotations

import pytest

from zentra_application_connector import PermissionDeniedError

from .conftest import CREDENTIALS, Harness


async def _registered(harness: Harness, actor):
    return await harness.service.register_source(
        actor, name="Warehouse", credentials=CREDENTIALS
    )


async def test_default_is_no_overrides_at_all(harness: Harness, admin) -> None:
    source = await _registered(harness, admin)

    overrides = await harness.service.list_agent_access(admin, source.data_source_id)

    assert overrides == ()


async def test_an_admin_may_hide_a_table(harness: Harness, admin) -> None:
    source = await _registered(harness, admin)

    view = await harness.service.set_table_agent_access(
        admin, source.data_source_id, "customers", agent_visible=False
    )

    assert view.table_name == "customers"
    assert view.field_name is None
    assert view.agent_visible is False

    overrides = await harness.service.list_agent_access(admin, source.data_source_id)
    assert [o.table_name for o in overrides] == ["customers"]


async def test_an_admin_may_hide_one_field(harness: Harness, admin) -> None:
    source = await _registered(harness, admin)

    view = await harness.service.set_field_agent_access(
        admin, source.data_source_id, "customers", "email", agent_visible=False
    )

    assert view.table_name == "customers"
    assert view.field_name == "email"
    assert view.agent_visible is False


async def test_toggling_the_same_table_twice_upserts_one_row(
    harness: Harness, admin
) -> None:
    source = await _registered(harness, admin)

    await harness.service.set_table_agent_access(
        admin, source.data_source_id, "customers", agent_visible=False
    )
    await harness.service.set_table_agent_access(
        admin, source.data_source_id, "customers", agent_visible=True
    )

    overrides = await harness.service.list_agent_access(admin, source.data_source_id)
    assert len(overrides) == 1
    assert overrides[0].agent_visible is True


async def test_a_member_cannot_toggle_a_table(
    harness: Harness, admin, member
) -> None:
    """Registration requires WRITE_ROLES too, so an admin registers the source
    the member then attempts to modify."""
    source = await _registered(harness, admin)

    with pytest.raises(PermissionDeniedError):
        await harness.service.set_table_agent_access(
            member, source.data_source_id, "customers", agent_visible=False
        )


async def test_a_viewer_cannot_toggle_a_field(
    harness: Harness, admin, viewer
) -> None:
    source = await _registered(harness, admin)

    with pytest.raises(PermissionDeniedError):
        await harness.service.set_field_agent_access(
            viewer, source.data_source_id, "customers", "email", agent_visible=False
        )


async def test_any_tenant_member_may_read_the_overrides(
    harness: Harness, admin, member
) -> None:
    source = await _registered(harness, admin)
    await harness.service.set_table_agent_access(
        admin, source.data_source_id, "customers", agent_visible=False
    )

    overrides = await harness.service.list_agent_access(member, source.data_source_id)
    assert len(overrides) == 1
