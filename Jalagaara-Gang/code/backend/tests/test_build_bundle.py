"""JAL-37/36/38: build_bundle assembles a schema-valid EvidenceBundle end to end."""
import json
from datetime import datetime
from pathlib import Path

import jsonschema
import pytest

from models import Factor, FactorDecomposition, Window
from rca import bundle

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "evidence_bundle.schema.json").read_text())

try:
    from data.client import run_query
    run_query("SELECT 1")
    _DB_UP = True
except Exception:  # noqa: BLE001
    _DB_UP = False


# ---- pure: ruled_out from flat, non-primary factors (JAL-31/36) ------------

def test_ruled_out_keys_off_the_factors_own_move_not_contribution():
    # ecpm has an inflated contribution_pct (99.0) but barely MOVED (-0.08%) -> still ruled out,
    # and its evidence must cite the move, not the blown-up contribution.
    fd = FactorDecomposition(primary_factor="requests", factors=[
        Factor(factor="requests", contribution_pct=5.0, from_=220000, to=126000),   # primary, big move
        Factor(factor="fill_rate", contribution_pct=0.1, from_=0.7850, to=0.7856),   # +0.08% -> flat
        Factor(factor="ecpm", contribution_pct=99.0, from_=2.480, to=2.478),         # -0.08% -> flat
    ])
    ruled = bundle._ruled_out(fd, "q_decompose")
    assert {r.hypothesis for r in ruled} == {"fill_rate", "ecpm_price"}   # primary excluded
    ecpm_ev = next(r for r in ruled if r.hypothesis == "ecpm_price").evidence
    assert "moved" in ecpm_ev and "99" not in ecpm_ev                    # cites the -0.08% move, not 9900%
    assert all(r.query_id == "q_decompose" for r in ruled)


def test_ruled_out_keeps_material_movers():
    # requests grew +4.3% (part of the masking) -> must NOT be cleared as 'within noise'
    fd = FactorDecomposition(primary_factor="fill_rate", factors=[
        Factor(factor="fill_rate", contribution_pct=0.5, from_=0.785, to=0.751),    # primary
        Factor(factor="requests", contribution_pct=-0.4, from_=808000, to=843000),  # +4.3% -> material
        Factor(factor="ecpm", contribution_pct=0.01, from_=2.475, to=2.4755),       # +0.02% -> flat
    ])
    ruled = bundle._ruled_out(fd, "q_decompose")
    assert {r.hypothesis for r in ruled} == {"ecpm_price"}


# ---- live end-to-end -------------------------------------------------------

pytestmark = pytest.mark.skipif(not _DB_UP, reason="needs live ClickHouse")


def test_case_a_bundle_localizes_and_validates_schema():
    window = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 26))
    b = bundle.build_bundle("fill_rate", window)
    jsonschema.validate(b.model_dump(mode="json", by_alias=True, exclude_none=True), SCHEMA)   # JAL-38
    assert b.localized_segment == {"os_version": "Android 15"}              # drill localizes the culprit
    assert b.anomaly.score != 0.0                                           # a real window-level z, not a 0 placeholder
    qids = {q.id for q in b.queries}
    assert all(node.query_id in qids for node in b.drilldown)               # every node traces to a query


def test_revenue_bundle_detects_and_names_primary_factor():
    window = Window(start=datetime(2026, 6, 21), end=datetime(2026, 6, 22))
    b = bundle.build_bundle("revenue", window)
    jsonschema.validate(b.model_dump(mode="json", by_alias=True, exclude_none=True), SCHEMA)
    assert b.anomaly.detected is True                     # revenue collapsed on Jun 21
    assert b.factor_decomposition.primary_factor == "requests"
