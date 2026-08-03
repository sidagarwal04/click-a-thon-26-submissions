"""JAL-80: narration as a separate step, with the LLM and store stubbed.

Three properties carry real scoring weight and are pinned here: the generation reattaches to
the investigation's existing trace, the guardrail verdict survives onto the bundle, and an LLM
failure degrades the answer instead of destroying a valid bundle.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import pipeline
from api.main import app
from models import EvidenceBundle, NarrativeVerification

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_bundle.json"


@pytest.fixture
def bundle() -> EvidenceBundle:
    b = EvidenceBundle.model_validate_json(FIXTURE.read_text())
    b.investigation_id = "inv-1"
    b.narrative = None
    b.narrative_verification = None
    return b


@pytest.fixture
def wired(monkeypatch, bundle):
    """Stub the store and the trace; record what each was asked to do."""
    state = {"saved": [], "spans": [], "loaded_trace": None}

    def fake_load(_id):
        return bundle if _id == "inv-1" else None

    def fake_meta(_id):
        state["loaded_trace"] = _id
        return "trace-xyz", "ctx-session-7"

    def fake_save(b, trace_id=None, session_id=None):
        state["saved"].append({"bundle": b, "trace_id": trace_id, "session_id": session_id})

    class FakeSpan:
        def __init__(self):
            self.updates = []

        def update(self, **kw):
            self.updates.append(kw)

    from contextlib import contextmanager

    @contextmanager
    def fake_span(trace_id, metric):
        span = FakeSpan()
        state["spans"].append({"trace_id": trace_id, "metric": metric, "span": span})
        yield span

    monkeypatch.setattr("api.pipeline.store.load_bundle", fake_load)
    monkeypatch.setattr("api.pipeline.store.load_meta", fake_meta)
    monkeypatch.setattr("api.pipeline.store.save_bundle", fake_save)
    monkeypatch.setattr("api.pipeline.narration_span", fake_span)
    return state


def _stub_llm(monkeypatch, prose="Revenue fell 15.2%.", passed=True, unverified=()):
    def fake_narrate(b):
        b.narrative = prose
        b.narrative_verification = NarrativeVerification(
            passed=passed, unverified_numbers=list(unverified))
        return b

    import narrator.narrate as narrate_module
    monkeypatch.setattr(narrate_module, "narrate", fake_narrate)


# ---- tracing ---------------------------------------------------------------

def test_generation_reattaches_to_the_investigation_trace(wired, monkeypatch):
    """Without the stored trace_id this would open a second, orphaned trace and the SQL
    steps would look unrelated to the LLM call."""
    _stub_llm(monkeypatch)

    pipeline.narrate_investigation("inv-1")

    assert wired["loaded_trace"] == "inv-1"
    assert wired["spans"][0]["trace_id"] == "trace-xyz"


def test_span_records_prose_and_guardrail_verdict(wired, monkeypatch):
    _stub_llm(monkeypatch, prose="Fill rate fell to 61%.")

    pipeline.narrate_investigation("inv-1")

    update = wired["spans"][0]["span"].updates[0]
    assert update["output"] == "Fill rate fell to 61%."
    assert update["metadata"]["guardrail_passed"] is True


# ---- guardrail -------------------------------------------------------------

def test_guardrail_verdict_lands_on_the_bundle(wired, monkeypatch):
    _stub_llm(monkeypatch, passed=False, unverified=["23.7"])

    result = pipeline.narrate_investigation("inv-1")

    assert result.narrative_verification.passed is False
    assert result.narrative_verification.unverified_numbers == ["23.7"]


def test_failed_guardrail_still_returns_the_bundle(wired, monkeypatch):
    """Surfaced, not silently dropped - the caller decides what to do about it."""
    _stub_llm(monkeypatch, passed=False, unverified=["999"])

    result = pipeline.narrate_investigation("inv-1")

    assert result is not None
    assert result.narrative is not None


# ---- resilience ------------------------------------------------------------

def test_llm_failure_does_not_destroy_the_bundle(wired, monkeypatch):
    """The numbers are already computed and scoreable; narration is presentation."""
    import narrator.narrate as narrate_module

    def boom(_b):
        raise RuntimeError("bedrock unavailable")

    monkeypatch.setattr(narrate_module, "narrate", boom)

    result = pipeline.narrate_investigation("inv-1")

    assert result is not None
    assert result.narrative is None
    assert len(result.queries) > 0          # evidence intact
    assert len(result.drilldown) > 0
    assert result.localized_segment != {}


def test_llm_failure_is_recorded_on_the_span(wired, monkeypatch):
    import narrator.narrate as narrate_module
    monkeypatch.setattr(narrate_module, "narrate",
                        lambda _b: (_ for _ in ()).throw(RuntimeError("boom")))

    pipeline.narrate_investigation("inv-1")

    update = wired["spans"][0]["span"].updates[0]
    assert update["level"] == "ERROR"
    assert "boom" in update["output"]["error"]


def test_unknown_investigation_returns_none(wired, monkeypatch):
    _stub_llm(monkeypatch)

    assert pipeline.narrate_investigation("nope") is None


def test_narrated_bundle_is_persisted_when_asked(wired, monkeypatch):
    _stub_llm(monkeypatch, prose="done")

    pipeline.narrate_investigation("inv-1", persist=True)

    assert wired["saved"][0]["bundle"].narrative == "done"
    assert wired["saved"][0]["trace_id"] == "trace-xyz"


def test_narrated_bundle_is_not_persisted_by_default(wired, monkeypatch):
    """Same lockdown contract as run_investigation/run_detection: `bundles` writes are
    seed-path-only. POST /narrate/{id} and the chat narration step both rely on this default
    rather than passing persist=True."""
    _stub_llm(monkeypatch, prose="done")

    pipeline.narrate_investigation("inv-1")

    assert wired["saved"] == []


def test_narrating_preserves_the_session_link(wired, monkeypatch):
    """Regression: investigations is a ReplacingMergeTree keyed on investigation_id, so a save
    that omits session_id replaces the row with an empty one rather than leaving it alone.
    That silently unlinked every chat-driven investigation from its conversation, and
    GET /chat/sessions/{id} then reported no investigations at all."""
    _stub_llm(monkeypatch)

    pipeline.narrate_investigation("inv-1", persist=True)

    assert wired["saved"][0]["session_id"] == "ctx-session-7"


# ---- HTTP ------------------------------------------------------------------

def test_endpoint_returns_narrated_bundle(wired, monkeypatch):
    _stub_llm(monkeypatch, prose="Revenue fell 15.2%.")

    res = TestClient(app).post("/narrate/inv-1")

    assert res.status_code == 200
    assert res.json()["narrative"] == "Revenue fell 15.2%."


def test_endpoint_404s_on_unknown_id(wired, monkeypatch):
    _stub_llm(monkeypatch)

    res = TestClient(app).post("/narrate/does-not-exist")

    assert res.status_code == 404
    assert "does-not-exist" in res.json()["detail"]


def test_chat_replies_contain_prose_not_a_placeholder(monkeypatch, bundle):
    """Regression: /investigate correctly strips the narrative, so the chat path has to
    narrate explicitly. Without that, every conversational reply was a placeholder."""
    narrated = bundle.model_copy(deep=True)
    narrated.narrative = "Fill rate collapsed on Android 15."

    monkeypatch.setattr("api.main.pipeline.run_investigation",
                        lambda *a, **kw: bundle)
    monkeypatch.setattr("api.main.pipeline.narrate_investigation",
                        lambda _id: narrated)
    monkeypatch.setattr("api.main.store.upsert_session", lambda *a, **kw: None)
    monkeypatch.setattr("api.main.store.add_turn", lambda *a, **kw: None)

    res = TestClient(app).post("/v1/chat/completions", json={
        "model": "rca-analyst",
        "messages": [{"role": "user", "content": "why did revenue drop on june 23?"}]})

    content = res.json()["choices"][0]["message"]["content"]
    assert content.startswith("Fill rate collapsed on Android 15.")
    assert "no narrative generated" not in content


def test_chat_degrades_readably_when_narration_fails(monkeypatch, bundle):
    """An LLM outage should not make the reply look like a broken system."""
    bundle.narrative = None
    monkeypatch.setattr("api.main.pipeline.run_investigation", lambda *a, **kw: bundle)
    monkeypatch.setattr("api.main.pipeline.narrate_investigation", lambda _id: bundle)
    monkeypatch.setattr("api.main.store.upsert_session", lambda *a, **kw: None)
    monkeypatch.setattr("api.main.store.add_turn", lambda *a, **kw: None)

    res = TestClient(app).post("/v1/chat/completions", json={
        "model": "rca-analyst",
        "messages": [{"role": "user", "content": "why did revenue drop on june 23?"}]})

    content = res.json()["choices"][0]["message"]["content"]
    assert "Narration unavailable" in content
    assert "Localized to:" in content       # the real evidence still ships


def test_endpoint_returns_200_when_the_llm_fails(wired, monkeypatch):
    """A Bedrock outage must not read as a broken investigation."""
    import narrator.narrate as narrate_module
    monkeypatch.setattr(narrate_module, "narrate",
                        lambda _b: (_ for _ in ()).throw(RuntimeError("no creds")))

    res = TestClient(app).post("/narrate/inv-1")

    assert res.status_code == 200
    assert res.json()["narrative"] is None
    assert res.json()["localized_segment"] != {}
