"""build_bundle emits the judge-facing phase story. Engine internals are stubbed —
this tests ORCHESTRATION of spans, not the math (the math has its own suites)."""
import pytest

from models import Anomaly, DrilldownNode, Factor, FactorDecomposition, Window
from narrator import tracing
from rca import bundle as bb
from tests.test_phase_tracing import FakeLangfuse


@pytest.fixture
def spans(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    return lf


@pytest.fixture
def stubbed_engine(monkeypatch):
    from datetime import datetime

    win = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 24))
    anomaly = Anomaly(detected=True, observed=90.0, expected=100.0, abs_delta=-10.0,
                      pct_delta=-0.1, score=-4.2, direction="drop")
    monkeypatch.setattr(bb, "_window_and_anomaly", lambda m, t: (win, anomaly, []))
    monkeypatch.setattr(bb, "baseline_window", lambda w: win)
    factors = FactorDecomposition(
        method="log_additive", primary_factor="fill_rate",
        factors=[Factor(factor="fill_rate", contribution_pct=0.9, **{"from": 0.8, "to": 0.6})],
    )
    monkeypatch.setattr(bb, "decompose", lambda m, w, b: (factors, [{"id": "q_d", "sql": "s", "result_summary": {}}]))
    node = DrilldownNode(depth=0, split_dimension="country", segment={"country": "IN"},
                        contribution_pct=0.87, status="culprit", query_id="q_0")
    monkeypatch.setattr(bb, "drill", lambda m, f, w, b: ([node], {"country": "IN"}, []))
    return win


def test_build_bundle_emits_phase_story_in_order(spans, stubbed_engine):
    bb.build_bundle("revenue", stubbed_engine)

    opened = [e[1] for e in spans.events if e[0] == "open"]
    assert opened == ["detect", "decompose", "drilldown", "ruled-out"]


def test_phase_verdicts_carry_the_why(spans, stubbed_engine):
    bb.build_bundle("revenue", stubbed_engine)

    closed = {e[1]: e[2] for e in spans.events if e[0] == "close"}
    detect_out = [u["output"] for u in closed["detect"] if "output" in u][0]
    assert detect_out["score"] == -4.2 and detect_out["direction"] == "drop"
    decomp_out = [u["output"] for u in closed["decompose"] if "output" in u][0]
    assert decomp_out["primary_factor"] == "fill_rate"
    drill_out = [u["output"] for u in closed["drilldown"] if "output" in u][0]
    assert drill_out["localized_segment"] == {"country": "IN"}
