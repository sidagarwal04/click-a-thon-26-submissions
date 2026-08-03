"""What a Tombstone may and may not say."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID

from zentra_domain_investigation import EvidenceCitation, Tombstone


def test_a_tombstone_carries_only_identity_category_and_time() -> None:
    """It exists to explain an absence without reconstructing what is absent.
    Every field it does not have is a field it cannot leak."""
    assert {field.name for field in fields(Tombstone)} == {
        "citation_id",
        "category",
        "erased_at",
    }


def test_a_tombstone_is_not_a_citation_with_blanks() -> None:
    """Sharing the type would make it one field-add away from leaking the
    thing it was built to hide."""
    citation_fields = {field.name for field in fields(EvidenceCitation)}
    tombstone_fields = {field.name for field in fields(Tombstone)}

    for leaky in ("metric", "filters", "period", "grain", "aggregate_value"):
        assert leaky in citation_fields
        assert leaky not in tombstone_fields


def test_a_tombstone_says_when_and_why_it_exists() -> None:
    erased = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)

    stone = Tombstone(
        citation_id=UUID("cc000000-0000-0000-0000-000000000001"),
        category="tenant_request",
        erased_at=erased,
    )

    assert stone.category == "tenant_request"
    assert stone.erased_at == erased
