"""Locks the shared metric formulas so every lane computes identically."""
import metrics as m


def test_python_ratios():
    assert m.fill_rate(61, 100) == 0.61
    assert m.ctr(2, 100) == 0.02
    assert m.ecpm(3.14, 1000) == 3.14
    assert m.rpr(100, 5000) == 0.02
    assert m.render_rate(98, 100) == 0.98


def test_safe_div_guards_zero():
    assert m.safe_div(5, 0) == 0.0
    assert m.ecpm(10, 0) == 0.0


def test_revenue_identity():
    requests, fr, e = 5_000_000, 0.61, 3.09
    assert abs(m.revenue_from_identity(requests, fr, e) - requests * fr * e / 1000) < 1e-6


def test_sql_builders():
    assert m.metric_sql("revenue", "events") == "sum(revenue)"
    assert m.ratio_sql("fill_rate", "events") == "sum(is_filled) / nullIf(count(*), 0)"
    assert m.ratio_sql("fill_rate", "rollup") == "sum(fills) / nullIf(sum(requests), 0)"
    assert m.metric_sql("ctr", "events") == "sum(is_click) / nullIf(sum(is_impression), 0)"
    assert m.metric_sql("ecpm", "rollup") == "sum(revenue) / nullIf(sum(impressions), 0) * 1000"
