"""Smoke tests for T3 bake-off and T4 legacy projection remediation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bakeoff import report_line, run as bakeoff_run
from ch import CH
from contracts import DDLProposal
from legacy import id_leading_tables, remediate

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "runs"


@pytest.fixture(scope="module")
def live() -> CH:
    ch = CH()
    ch.run_select("SELECT 1")
    return ch


def _latest_proposal(table_name: str) -> DDLProposal | None:
    if not ARTIFACTS.exists():
        return None
    runs = sorted(ARTIFACTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        p = r / "proposal.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        if data.get("table_name") == table_name:
            return DDLProposal.model_validate(data)
    return None


def test_id_leading_tables_finds_legacy_eight(live: CH) -> None:
    found = id_leading_tables(live)
    names = {r["name"] for r in found}
    assert "destination_card_clicked" in names
    assert all(r["sorting_key"].startswith("id") for r in found)
    # Must not flag our own feature tables.
    assert not any(n.startswith("f_") for n in names)


def test_bakeoff_runs_and_drops_straw(live: CH) -> None:
    prop = _latest_proposal("f_instant_forex_events")
    if prop is None or not live.table_exists("f_instant_forex_events"):
        pytest.skip("instant_forex table / proposal not present")
    result = bakeoff_run(prop, live)
    assert result["ok"] is True
    assert "Bake-off" in prop.rationale["order_by"]
    assert not live.table_exists(f"bake_{prop.semantics.feature_slug}_straw")
    assert "bake-off" in report_line(result)


def test_legacy_projection_reduces_or_matches_bytes(live: CH) -> None:
    """On destination_card_clicked the projection must be selectable and not regress."""
    if not live.table_exists("destination_card_clicked"):
        pytest.skip("legacy table missing")
    result = remediate(live, "destination_card_clicked", dry_run=False)
    assert result["added"] or result["materialized"]
    assert "p_funnel" in result["after_explain"]
    before_b = int(result["before"].get("read_bytes", 0))
    after_b = int(result["after"].get("read_bytes", 0))
    assert before_b > 0 and after_b > 0
    # Allow noise; forbid a large regression.
    assert after_b <= before_b * 1.05
