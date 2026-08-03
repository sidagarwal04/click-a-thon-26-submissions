"""JAL-73: row mapping for the bundles/investigations store, exercised without a live database.

`bundles` is the traceability table — one row per detection run, `bundle` column the source
of truth, flattened columns for SQL/dashboard. `investigations` is the lean session record
referencing its evidence via bundle_id. These tests lock both halves of that contract.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data import store
from models import EvidenceBundle

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_bundle.json"


@pytest.fixture
def bundle() -> EvidenceBundle:
    return EvidenceBundle.model_validate_json(FIXTURE.read_text())


def _row(bundle) -> dict:
    return dict(zip(store._BUNDLE_COLUMNS, store._to_bundle_row(bundle)))


def _inv_row(bundle, trace_id=None, session_id=None) -> dict:
    return dict(zip(
        store._INVESTIGATION_COLUMNS,
        store._to_investigation_row(bundle.investigation_id, trace_id, session_id, bundle.created_at),
    ))


def test_bundle_row_matches_column_order(bundle):
    assert len(store._to_bundle_row(bundle)) == len(store._BUNDLE_COLUMNS)


def test_investigation_row_matches_column_order(bundle):
    assert len(store._to_investigation_row("x", None, None, bundle.created_at)) == len(
        store._INVESTIGATION_COLUMNS
    )


def test_bundle_row_flattens_queryable_fields(bundle):
    row = _row(bundle)
    assert row["investigation_id"] == bundle.investigation_id
    assert row["metric"] == bundle.metric
    assert row["window_start"] == bundle.target_window.start.replace(tzinfo=None)
    assert row["primary_factor"] == bundle.factor_decomposition.primary_factor
    assert json.loads(row["localized_segment"]) == bundle.localized_segment
    assert row["direction"] == bundle.anomaly.direction
    assert row["observed"] == bundle.anomaly.observed
    assert row["ruled_out_count"] == len(bundle.ruled_out)


def test_is_anomaly_and_narrated_are_uint8_flags(bundle):
    row = _row(bundle)
    assert row["is_anomaly"] == 1
    assert row["narrated"] == 1  # the fixture ships with a narrative

    bundle.narrative = None
    bundle.anomaly.detected = False
    row = _row(bundle)
    assert row["narrated"] == 0
    assert row["is_anomaly"] == 0  # a "checked, normal" traceability row


def test_investigation_row_references_bundle_by_id(bundle):
    """The investigation record carries no evidence — just the bundle_id pointer."""
    row = _inv_row(bundle)
    assert row["bundle_id"] == bundle.investigation_id
    assert row["investigation_id"] == bundle.investigation_id
    assert "metric" not in row and "bundle" not in row


def test_trace_and_session_default_to_empty_string_not_null(bundle):
    """ClickHouse String columns are non-nullable here, so absent ids must be ''."""
    row = _inv_row(bundle)
    assert row["trace_id"] == ""
    assert row["session_id"] == ""


def test_trace_and_session_are_persisted_when_given(bundle):
    row = _inv_row(bundle, trace_id="trace-abc", session_id="ctx-123")
    assert row["trace_id"] == "trace-abc"
    assert row["session_id"] == "ctx-123"


def test_datetimes_are_naive_for_clickhouse(bundle):
    """ClickHouse DateTime carries no timezone; aware values must be stripped so a
    round-trip compares equal instead of silently shifting."""
    row = _row(bundle)
    for key in ("created_at", "updated_at", "window_start", "window_end"):
        assert row[key].tzinfo is None, f"{key} still tz-aware"
    inv = _inv_row(bundle)
    for key in ("created_at", "updated_at"):
        assert inv[key].tzinfo is None, f"investigations.{key} still tz-aware"


def test_naive_helper_leaves_naive_untouched():
    naive = datetime(2026, 7, 4, 10, 0, 0)
    assert store._naive(naive) is naive
    aware = datetime(2026, 7, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert store._naive(aware) == naive


def test_bundle_survives_a_full_round_trip(bundle):
    """Serialise into the row, rehydrate from it, and confirm nothing was lost."""
    row = _row(bundle)
    restored = store._bundle_from_row(row)
    assert restored.investigation_id == bundle.investigation_id
    assert restored.localized_segment == bundle.localized_segment
    assert restored.narrative == bundle.narrative
    assert len(restored.queries) == len(bundle.queries)
    assert len(restored.drilldown) == len(bundle.drilldown)
    assert len(restored.ruled_out) == len(bundle.ruled_out)
    assert restored.model_dump_json() == bundle.model_dump_json()


def test_round_trip_preserves_a_bundle_with_no_narrative(bundle):
    """The investigate/narrate split means bundles are stored before prose exists."""
    bundle.narrative = None
    bundle.narrative_verification = None
    restored = store._bundle_from_row(_row(bundle))
    assert restored.narrative is None
    assert restored.narrative_verification is None
