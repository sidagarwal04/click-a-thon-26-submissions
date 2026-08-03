from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from zentra_domain_investigation import (
    Group,
    OrganizationNameError,
    Project,
    normalize_organization_name,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def test_workspace_names_are_display_safe_and_normalized_for_uniqueness() -> None:
    assert normalize_organization_name("  Revenue\u00a0  Operations  ") == (
        "Revenue Operations",
        "revenue operations",
    )


@pytest.mark.parametrize("name", ["", "   ", "x" * 101, "bad\x00name"])
def test_workspace_names_reject_invalid_values(name: str) -> None:
    with pytest.raises(OrganizationNameError):
        normalize_organization_name(name)


def test_group_archive_and_restore_preserve_identity_and_name() -> None:
    group = Group.create(
        group_id=uuid4(),
        tenant_id=uuid4(),
        name="Finance",
        now=NOW,
    )

    group.archive(NOW)
    assert group.archived_at == NOW
    group.restore(NOW)

    assert group.archived_at is None
    assert group.name == "Finance"
    assert group.normalized_name == "finance"


def test_project_rename_updates_display_and_normalized_names() -> None:
    project = Project.create(
        project_id=uuid4(),
        tenant_id=uuid4(),
        group_id=uuid4(),
        name="Weekly Review",
        now=NOW,
    )

    project.rename("  Monthly   Review ", NOW)

    assert project.name == "Monthly Review"
    assert project.normalized_name == "monthly review"
    assert project.updated_at == NOW


def test_project_activity_advances_independently_of_metadata_updates() -> None:
    project = Project.create(
        project_id=uuid4(),
        tenant_id=uuid4(),
        group_id=uuid4(),
        name="Weekly Review",
        now=NOW,
    )
    later = datetime(2026, 8, 2, tzinfo=UTC)

    project.record_activity(later)

    assert project.latest_activity_at == later
    assert project.updated_at == NOW
