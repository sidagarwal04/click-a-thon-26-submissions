"""What the chat model is allowed to see about an incident, and how big that is.

Measured before this was capped: the prompt for one real incident was 975,728
characters -- roughly a quarter of a million tokens of prefill on EVERY turn -- made of
900,412 characters of absorbed clusters (2,520 of them), 46,817 characters of verbatim
SQL the system prompt forbids the model to compute from, and 10,512 of member rows.

Two things are pinned here, and the second matters more than the first: that the payload
is small, and that every cap still reports its own true total. A truncated list the
model reads as complete is how "3 apps breached" gets said about 170 -- the same failure
gotcha 37 records for the incident queue's "0 suppressed".
"""

import json

import pytest

from api.main import _incident_chat_evidence, _investigation_evidence_for_llm
from engine import monitor_store
from engine.config import settings


def _fake_incident(absorbed_n: int, members_n: int) -> dict:
    return {
        "incident_id": "inc-test", "signature": "S4", "mechanism": "demand outage",
        "owner": "demand", "root_scope_type": "os_family", "root_scope_value": "Android",
        "root_metric": "fill_rate", "grain": "1d", "direction": "below",
        "impact_usd": 48.84, "impact_usd_per_day": 24.42, "member_event_count": 765,
        "absorbed": [
            {"root": f"dim_{i}=v", "metric": "revenue", "impact_usd": float(i),
             "events": 3, "reason": "x" * 300}
            for i in range(absorbed_n)
        ],
        "members": [
            {"metric": "fill_rate", "scope_type": "app", "scope_value": f"app_{i}",
             "impact_usd": float(i), "grain": "1d"}
            for i in range(members_n)
        ],
        "evidence": {"metric": "revenue", "current_value": 1.0,
                     "queries": [{"step": "rank:x", "sql": "SELECT " + "col, " * 500}]},
    }


def test_sql_trace_never_reaches_the_model():
    """EvidenceBundle.to_llm_json() already excludes `queries` for the narrator. Chat
    reads the persisted dict back from ClickHouse and so cannot call that method --
    it must apply the same rule itself, or the guardrail holds on one LLM surface and
    not the other."""
    evidence = {"metric": "revenue", "current_value": 1.0, "queries": [{"sql": "SELECT 1"}]}
    stripped = _investigation_evidence_for_llm(evidence)

    assert "queries" not in stripped
    assert stripped["metric"] == "revenue" and stripped["current_value"] == 1.0
    assert "queries" in evidence, "the caller's dict must not be mutated"
    assert _investigation_evidence_for_llm(None) is None


def test_previews_are_capped_and_state_their_true_totals():
    payload = _incident_chat_evidence(_fake_incident(absorbed_n=2520, members_n=500))

    assert len(payload["absorbed"]) == settings.absorbed_preview_limit
    assert payload["absorbed_total"] == 2520
    assert len(payload["members_shown"]) == settings.chat_members_preview_limit
    # The incident's OWN count, not the length of the fetched list -- get_incident caps
    # its member query at 500, so len(members) would describe a 765-member incident as
    # having 500.
    assert payload["members_total"] == 765
    assert "2520" in payload["truncation_note"] and "765" in payload["truncation_note"]
    assert "queries" not in payload["investigation_evidence"]


def test_small_incident_is_not_padded_or_truncated():
    payload = _incident_chat_evidence(_fake_incident(absorbed_n=3, members_n=4))

    assert len(payload["absorbed"]) == 3 and payload["absorbed_total"] == 3
    assert len(payload["members_shown"]) == 4


@pytest.mark.integration
def test_real_incident_prompt_stays_small():
    """Against the actual worst incident in the database, not a fixture -- the one whose
    prompt measured 975,728 characters."""
    rows = monitor_store.list_incidents(limit=5)
    if not rows:
        pytest.skip("no incidents persisted yet")

    for row in rows:
        incident = monitor_store.get_incident(row["incident_id"])
        size = len(json.dumps(_incident_chat_evidence(incident), default=str))
        assert size < 60_000, f"incident {row['incident_id']} builds a {size:,}-char prompt"
