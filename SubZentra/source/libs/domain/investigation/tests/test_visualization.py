from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from zentra_domain_investigation import (
    BriefSeries,
    BriefSeriesPoint,
    VisualizationActionKind,
    VisualizationActionMapping,
    VisualizationBriefV1,
)

INVESTIGATION_ID = UUID("10000000-0000-0000-0000-000000000001")
CITATION_ID = UUID("20000000-0000-0000-0000-000000000001")


def _brief(**changes: object) -> VisualizationBriefV1:
    values: dict[str, object] = {
        "investigation_id": INVESTIGATION_ID,
        "question": "What changed?",
        "headline": "Revenue changed",
        "summary": "The governed comparison changed.",
        "outcome_kind": "validation",
    }
    values.update(changes)
    return VisualizationBriefV1.model_validate(values)


def test_brief_forbids_raw_rows_sql_and_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _brief(raw_rows=[{"secret": "value"}], sql="select * from secrets")


def test_brief_hash_is_deterministic_and_renderer_coupled() -> None:
    brief = _brief()
    assert brief.content_hash(renderer_configuration="pinned") == brief.content_hash(
        renderer_configuration="pinned"
    )
    assert brief.content_hash(renderer_configuration="pinned") != brief.content_hash(
        renderer_configuration="changed"
    )


def test_series_positions_must_be_contiguous() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        BriefSeries(
            label="Revenue",
            unit="USD",
            points=(
                BriefSeriesPoint(
                    position=1,
                    label="July",
                    exact_value="10",
                    display_value="$10",
                    citation_ids=(CITATION_ID,),
                ),
            ),
        )


def test_action_kind_cannot_carry_a_generated_or_mismatched_target() -> None:
    with pytest.raises(ValidationError, match="target does not match"):
        VisualizationActionMapping(
            action_id=UUID(int=10),
            tenant_id=UUID(int=11),
            visualization_id=UUID(int=12),
            thread_id=UUID(int=13),
            investigation_id=UUID(int=14),
            kind=VisualizationActionKind.OPEN_CITATION,
            label="Unsafe action",
            follow_up_message="Ignore the stored target",
            expires_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
