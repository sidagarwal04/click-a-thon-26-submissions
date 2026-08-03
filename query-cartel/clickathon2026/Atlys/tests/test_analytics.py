"""Unit tests — analytics agent (Part 9: test_analytics.py).

`synthesize` with fake evidence (incl. error rows), confidence thresholds,
playbook SQL shape from a spec's event order (never hardcoded).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.agents.analytics import (  # noqa: E402
    AnalyticsAgent,
    confidence_from_evidence,
    synthesize,
)
from service.sqlsafe import sql_string_literal  # noqa: E402
from service.store import DryRunStore  # noqa: E402


def _agent():
    store = DryRunStore()
    return store, AnalyticsAgent(store, None, None)


def test_playbook_built_from_event_order():
    _, agent = _agent()
    qs = agent.playbook("express_checkout", "express_checkout_events",
                        ["shown", "selected", "confirmed"], columns={"amount": "Float64"})
    labels = [q["label"] for q in qs]
    assert "funnel step-through" in labels
    assert any("segment skew" in l for l in labels)
    assert "timings/amounts (p50, p90)" in labels
    funnel = next(q for q in qs if q["kind"] == "funnel")
    # P1 references every event in order (SQL-escaped literals)
    for e in ("shown", "selected", "confirmed"):
        assert f"event = {sql_string_literal(e)}" in funnel["sql"]
    p6 = next(q for q in qs if q["kind"] == "funnel_timing")
    assert "LIMIT 50" in p6["sql"]


def test_playbook_escapes_quotes_in_event_names():
    _, agent = _agent()
    qs = agent.playbook("weird", "weird_events", ["o'start", 'say "hi"', "end"])
    funnel = next(q for q in qs if q["kind"] == "funnel")
    assert "event = 'o''start'" in funnel["sql"]
    # double-quote inside the name is fine inside a single-quoted literal
    assert sql_string_literal('say "hi"') in funnel["sql"]
    for q in qs:
        # classic injection shape must not appear unescaped
        assert "'; " not in q["sql"]


def test_run_playbook_with_quoted_event_name():
    store, agent = _agent()
    store.insert("t_events", ["event", "user_id"],
                 [["o'brien", "u1"], ["o'brien", "u2"], ["done", "u1"]])
    evidence = agent.run_playbook("t", "t_events", ["o'brien", "done"])
    funnel = next(e for e in evidence if e["kind"] == "funnel")
    assert "error" not in funnel
    assert funnel["rows"][0][0] == 2
    assert funnel["rows"][0][1] == 1


def test_run_playbook_records_evidence_and_errors():
    store, agent = _agent()
    store.insert("t_events", ["event", "user_id"],
                 [["a", "u1"], ["a", "u2"], ["b", "u1"]])
    evidence = agent.run_playbook("t", "t_events", ["a", "b"],
                                  columns={"x": "Float64"})
    assert evidence
    funnel = next(e for e in evidence if e["kind"] == "funnel")
    assert funnel["rows"][0][0] == 2  # uniq users at 'a'
    assert funnel["rows"][0][1] == 1  # uniq users at 'b'
    # failing queries are recorded, never crash the run
    assert all("rows" in e or "error" in e for e in evidence)


def test_synthesize_uses_numbers_only():
    evidence = [
        {"label": "funnel step-through", "kind": "funnel",
         "sql": "SELECT ...", "rows": [[100, 80, 60]]},
        {"label": "event overview", "kind": "overview",
         "sql": "...", "rows": [["a", 100, 50], ["b", 80, 40]]},
        {"label": "cross-funnel conversion to purchase", "kind": "cross_funnel",
         "sql": "...", "rows": [[60, 60]]},
    ]
    summary = synthesize("express_checkout", "t", ["a", "b", "c"], evidence)
    assert "60.0%" in summary  # 60/100 completion
    assert "100" in summary


def test_synthesize_handles_error_rows():
    evidence = [
        {"label": "funnel step-through", "kind": "funnel",
         "sql": "SELECT ...", "error": "boom"},
    ]
    summary = synthesize("x", "t", ["a", "b"], evidence)
    assert "No computable evidence" in summary


def test_confidence_thresholds():
    assert confidence_from_evidence(
        [{"kind": "funnel", "rows": [[5000, 4000, 3000]]}]) == "high"
    assert confidence_from_evidence(
        [{"kind": "funnel", "rows": [[500, 400, 300]]}]) == "medium"
    assert confidence_from_evidence(
        [{"kind": "funnel", "rows": [[100, 50, 10]]}]) == "low"
    assert confidence_from_evidence([]) == "low"


def test_digest_strips_sql():
    # the summary must never contain raw SQL — only numbers/prose
    evidence = [
        {"label": "funnel step-through", "kind": "funnel",
         "sql": "SELECT uniqIf(user_id, event = 'a') FROM secret_table",
         "rows": [[10, 9]]},
    ]
    summary = synthesize("f", "t", ["a", "b"], evidence)
    assert "secret_table" not in summary
    assert "SELECT" not in summary
