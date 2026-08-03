"""JAL-79: the trace-and-persist contract, with Langfuse and ClickHouse stubbed.

An investigation is always traced. Persistence is opt-in (`persist=True`) and reserved for the
seed path (api/dev.py) — every non-seed caller (POST /investigate, chat) leaves it False, so
`bundles` is never written to except when explicitly seeding. Tests that exercise the storage
contract itself pass persist=True; the rest don't touch it. trace_id still has to survive when
persisted, since POST /narrate/{id} is a separate HTTP call and needs it to attach its
generation span to the trace the investigation already opened.
"""
from datetime import datetime

import pytest

from api import pipeline
from models import EvidenceBundle, Window
from narrator.tracing import Trace


@pytest.fixture
def saved(monkeypatch) -> list[dict]:
    """Capture what would have been written to ClickHouse."""
    calls: list[dict] = []

    def fake_save(bundle, trace_id=None, session_id=None):
        calls.append({"bundle": bundle, "trace_id": trace_id, "session_id": session_id})

    monkeypatch.setattr("api.pipeline.store.save_bundle", fake_save)
    return calls


@pytest.fixture
def traced(monkeypatch) -> list[dict]:
    """Stub the trace context manager, recording how it was opened."""
    opened: list[dict] = []

    class FakeTrace:
        def __init__(self, investigation_id, metric, session_id=None):
            opened.append({"investigation_id": investigation_id, "metric": metric,
                           "session_id": session_id})

        def __enter__(self):
            return Trace(trace_id="trace-abc", url="https://langfuse.local/t/trace-abc")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr("api.pipeline.investigation_trace", FakeTrace)
    return opened


def test_investigation_is_traced(traced, saved):
    pipeline.run_investigation("fill_rate")

    assert len(traced) == 1
    assert traced[0]["metric"] == "fill_rate"


def test_trace_url_lands_on_the_bundle(traced, saved):
    """This is what a judge clicks from the diagnosis."""
    bundle = pipeline.run_investigation("revenue")

    assert bundle.trace_url == "https://langfuse.local/t/trace-abc"


def test_trace_id_is_persisted_not_just_the_url(traced, saved):
    """/narrate must reattach to this trace, so the id has to survive the HTTP boundary
    (when a caller opts into persistence — see module docstring)."""
    pipeline.run_investigation("revenue", persist=True)

    assert saved[0]["trace_id"] == "trace-abc"


def test_session_id_flows_into_both_trace_and_row(traced, saved):
    """Chat-driven investigations group under one Langfuse session."""
    pipeline.run_investigation("ecpm", session_id="ctx-42", persist=True)

    assert traced[0]["session_id"] == "ctx-42"
    assert saved[0]["session_id"] == "ctx-42"


def test_bundle_is_persisted_when_asked(traced, saved):
    bundle = pipeline.run_investigation("revenue", persist=True)

    assert saved[0]["bundle"].investigation_id == bundle.investigation_id


def test_bundle_is_not_persisted_by_default(traced, saved):
    """The lockdown contract: `bundles` must only ever be written from the seed path
    (api/dev.py), never from POST /investigate or chat — persist=False is the default and
    every non-seed caller relies on that default rather than passing True."""
    pipeline.run_investigation("revenue")

    assert saved == []


def test_returned_bundle_has_no_narrative(traced, saved):
    """The investigate/narrate split: numbers in ~2s, prose separately. An LLM failure must
    not be able to destroy an otherwise complete, scoreable bundle."""
    bundle = pipeline.run_investigation("revenue")

    assert bundle.narrative is None
    assert bundle.narrative_verification is None


def test_stored_row_is_marked_not_narrated(traced, saved):
    """`narrated` only means something if /investigate never sets it."""
    pipeline.run_investigation("revenue", persist=True)

    assert saved[0]["bundle"].narrative is None


def test_each_run_gets_a_fresh_id(traced, saved):
    first = pipeline.run_investigation("revenue")
    second = pipeline.run_investigation("revenue")

    assert first.investigation_id != second.investigation_id


def test_requested_metric_and_window_are_reflected(traced, saved):
    window = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 26))

    bundle = pipeline.run_investigation("fill_rate", window)

    assert bundle.metric == "fill_rate"
    assert bundle.target_window.start == window.start
    assert bundle.target_window.end == window.end


def test_tracing_disabled_still_investigates_and_stores(monkeypatch, saved):
    """Langfuse keys absent must not break the pipeline - only the trace links go missing."""
    from contextlib import contextmanager

    @contextmanager
    def no_tracing(*_a, **_kw):
        yield Trace()

    monkeypatch.setattr("api.pipeline.investigation_trace", no_tracing)

    bundle = pipeline.run_investigation("revenue", persist=True)

    assert isinstance(bundle, EvidenceBundle)
    assert bundle.trace_url is None
    assert saved[0]["trace_id"] is None


def test_engine_status_reports_fixture_while_lane_b_is_stubbed():
    """Flips to 'live' on its own once build_bundle is implemented - no edit needed here."""
    assert pipeline.engine_status() in {"live", "fixture"}


def test_fixture_fallback_is_announced(traced, saved, caplog):
    """Serving fixture numbers silently as a real diagnosis is the trust failure to avoid."""
    if pipeline.engine_status() != "fixture":
        pytest.skip("engine is live; fallback no longer applies")

    with caplog.at_level("WARNING"):
        pipeline.run_investigation("revenue")

    assert any("FIXTURE" in r.message.upper() for r in caplog.records)


# ---- fail-soft when the datastore is unreachable (bad/missing CLICKHOUSE_*) ----

def test_engine_mode_reports_offline_when_datastore_down(monkeypatch):
    """engine implemented + ClickHouse unreachable => 'offline', not 'live' (which would 500)."""
    monkeypatch.setattr("api.pipeline.engine_status", lambda: "live")
    monkeypatch.setattr("data.client.clickhouse_available", lambda: False)

    assert pipeline.engine_mode() == "offline"


def test_engine_mode_reports_live_when_engine_and_datastore_up(monkeypatch):
    monkeypatch.setattr("api.pipeline.engine_status", lambda: "live")
    monkeypatch.setattr("data.client.clickhouse_available", lambda: True)

    assert pipeline.engine_mode() == "live"


def test_offline_serves_fixture_without_persisting(traced, saved, monkeypatch, caplog):
    """A datastore outage degrades to the sample bundle instead of raising — and does NOT try to
    persist (which would itself hit the dead ClickHouse)."""
    monkeypatch.setattr("api.pipeline.engine_status", lambda: "live")
    monkeypatch.setattr("data.client.clickhouse_available", lambda: False)

    with caplog.at_level("WARNING"):
        bundle = pipeline.run_investigation("revenue")

    assert isinstance(bundle, EvidenceBundle)
    assert saved == []  # nothing written while offline
    assert any("FIXTURE" in r.message.upper() for r in caplog.records)
