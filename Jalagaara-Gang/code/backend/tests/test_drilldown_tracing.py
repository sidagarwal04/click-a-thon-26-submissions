"""drill() emits one span per depth whose output is the descend/stop decision."""
import pytest

from narrator import tracing
from rca import drilldown as dd
from tests.test_phase_tracing import FakeLangfuse


@pytest.fixture
def spans(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    return lf


@pytest.fixture
def two_level_engine(monkeypatch):
    """Stub the SQL layer: depth 0 finds country=IN (87%, lift 3.0); depth 1 finds nothing."""
    pops = {0: ({"revenue": 90.0}, {"revenue": 100.0}), 1: ({"revenue": 9.0}, {"revenue": 20.0})}
    monkeypatch.setattr(dd, "_pop", lambda w, p, depth: (*pops[depth], "SQL"))
    monkeypatch.setattr(dd, "measure_natural_noise", lambda f: 0.001)

    def by_dim(dim, w, p, depth):
        if depth == 0 and dim == "country":
            return [("IN", {"revenue": 9.0}, {"revenue": 20.0})], "SQL"
        return [], "SQL"

    monkeypatch.setattr(dd, "_by_dim", by_dim)
    monkeypatch.setattr(dd, "_score", lambda f, po, pe, so, se: (0.87, 3.0))
    monkeypatch.setattr(dd, "_metric_from_sums", lambda f, s: s.get("revenue", 0.0))
    return pops


def test_each_depth_gets_a_decision_span(spans, two_level_engine):
    from datetime import datetime

    from models import Window

    w = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 24))
    dd.drill("revenue", "revenue", w, w)

    def final_name(close_event):
        names = [u["name"] for u in close_event[2] if "name" in u]
        return names[-1] if names else close_event[1]

    closes = [e for e in spans.events if e[0] == "close"]
    assert final_name(closes[0]) == "depth-0:country"
    assert final_name(closes[1]) == "depth-1:stop"

    closed = {final_name(e): e[2] for e in closes}
    d0 = [u["output"] for u in closed["depth-0:country"] if "output" in u][0]
    assert d0["decision"] == "descend" and d0["winner"] == {"country": "IN"}
    assert d0["contribution_pct"] == 0.87 and d0["lift"] == 3.0
    d1 = [u["output"] for u in closed["depth-1:stop"] if "output" in u][0]
    assert d1["decision"] == "stop"
