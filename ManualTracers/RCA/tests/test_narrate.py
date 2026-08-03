import pytest

from app.narrate import narrate

pytestmark = pytest.mark.anyio

# just enough shape to make ledger.get("findings") truthy — the fallback-without-a-key
# path below doesn't need the full realistic ledger (that's test_grounding.py's job)
MINIMAL_LEDGER_WITH_FINDINGS = {
    "metric_id": "fill_rate",
    "window": {"start": "a", "end": "b"},
    "decomposition": None,
    "findings": [
        {
            "factor": "fill_rate",
            "global": {"actual": 0.1, "expected": 0.2, "hours": 1, "peak_abs_z": 5.0},
            "candidates": [],
            "verdict": "broad_based",
            "ruled_out": [],
        }
    ],
    "verdict": "broad_based",
}


async def test_narrate_uses_template_when_alert_did_not_reproduce():
    ledger = {
        "metric_id": "revenue",
        "window": {"start": "a", "end": "b"},
        "verdict": "not_reproducible",
    }
    result = await narrate(ledger)
    assert result["source"] == "template"
    assert "not_reproducible" in result["narrative"]


async def test_narrate_falls_back_to_template_without_a_gemini_key():
    # RCA/tests/conftest.py forces GEMINI_API_KEY empty for the whole test session, before
    # Settings is ever cached — this exercises the real "no key configured" path, not a
    # per-test monkeypatch (Settings is memoized, so patching os.environ after the fact
    # wouldn't change an already-resolved settings.gemini_api_key anyway).
    result = await narrate(MINIMAL_LEDGER_WITH_FINDINGS)
    assert result["source"] == "template"
