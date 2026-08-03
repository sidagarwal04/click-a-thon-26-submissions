"""JAL-81: GET /bundle/{id} and GET /bundles, with the store stubbed out.

The store itself is covered by test_store.py against a real round-trip; here we only
pin the HTTP contract — status codes, shapes, and that a missing id is a clean 404
rather than a 500.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from models import EvidenceBundle

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_bundle.json"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def bundle() -> EvidenceBundle:
    return EvidenceBundle.model_validate_json(FIXTURE.read_text())


def test_health_reports_component_wiring(client):
    """Judges run this locally, where failures are silent: a fresh Langfuse has no keys and
    tracing no-ops, and the engine may still be stubbed. /health has to say so."""
    payload = client.get("/health").json()

    assert payload["ok"] is True
    assert payload["engine"] in {"live", "fixture"}
    assert "enabled" in payload["langfuse"]
    assert "host" in payload["langfuse"]


def test_get_bundle_returns_stored_bundle(client, bundle, monkeypatch):
    monkeypatch.setattr("api.main.store.load_bundle", lambda _id: bundle)

    res = client.get(f"/bundle/{bundle.investigation_id}")

    assert res.status_code == 200
    assert res.json()["investigation_id"] == bundle.investigation_id
    assert res.json()["localized_segment"] == bundle.localized_segment


def test_get_bundle_passes_the_id_through(client, bundle, monkeypatch):
    seen = {}

    def fake_load(investigation_id):
        seen["id"] = investigation_id
        return bundle

    monkeypatch.setattr("api.main.store.load_bundle", fake_load)

    client.get("/bundle/abc-123")

    assert seen["id"] == "abc-123"


def test_get_bundle_unknown_id_is_404_not_500(client, monkeypatch):
    monkeypatch.setattr("api.main.store.load_bundle", lambda _id: None)

    res = client.get("/bundle/does-not-exist")

    assert res.status_code == 404
    assert "does-not-exist" in res.json()["detail"]


def test_get_bundle_preserves_queries_for_traceability(client, bundle, monkeypatch):
    """Every number in a diagnosis must trace to queries[]; the transport must not drop it."""
    monkeypatch.setattr("api.main.store.load_bundle", lambda _id: bundle)

    payload = client.get(f"/bundle/{bundle.investigation_id}").json()

    assert len(payload["queries"]) == len(bundle.queries)
    assert payload["queries"][0]["sql"] == bundle.queries[0].sql
    assert len(payload["ruled_out"]) == len(bundle.ruled_out)


def test_list_bundles_counts_rows(client, monkeypatch):
    rows = [{"investigation_id": "a", "metric": "revenue"},
            {"investigation_id": "b", "metric": "fill_rate"}]
    monkeypatch.setattr("api.main.store.list_investigations", lambda limit: rows)

    payload = client.get("/bundles").json()

    assert payload["count"] == 2
    assert payload["investigations"] == rows


def test_list_bundles_forwards_limit(client, monkeypatch):
    seen = {}

    def fake_list(limit):
        seen["limit"] = limit
        return []

    monkeypatch.setattr("api.main.store.list_investigations", fake_list)

    client.get("/bundles?limit=7")

    assert seen["limit"] == 7


def test_list_bundles_empty_is_not_an_error(client, monkeypatch):
    # Datastore reachable but no rows yet: 200 with an empty list and engine:"live".
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.list_investigations", lambda limit: [])

    res = client.get("/bundles")

    assert res.status_code == 200
    assert res.json() == {"count": 0, "investigations": [], "engine": "live"}


def test_list_bundles_offline_fails_soft(client, monkeypatch):
    # Datastore unreachable: fail soft (200 + engine:"offline"), never a 500.
    monkeypatch.setattr("api.main.clickhouse_available", lambda: False)

    res = client.get("/bundles")

    assert res.status_code == 200
    assert res.json() == {"count": 0, "investigations": [], "engine": "offline"}


def test_get_trace_returns_the_timeline(client, monkeypatch):
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.load_trace_view", lambda _id: None)
    monkeypatch.setattr("api.main.store.save_trace_view", lambda *a: None)
    monkeypatch.setattr("api.main.store.load_meta", lambda _id: ("trace-1", None))
    monkeypatch.setattr("api.main.trace_read.trace_view",
                        lambda tid: {"available": True, "total_ms": 2876, "steps": []})

    payload = client.get("/trace/abc-123").json()

    assert payload["available"] is True
    assert payload["total_ms"] == 2876


def test_get_trace_is_200_even_when_unavailable(client, monkeypatch):
    """The drawer shows a reason; a missing trace must never 500 the dashboard."""
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.load_trace_view", lambda _id: None)
    monkeypatch.setattr("api.main.store.load_meta", lambda _id: (None, None))

    res = client.get("/trace/abc-123")

    assert res.status_code == 200
    assert res.json()["available"] is False


def test_trace_prefers_the_stored_snapshot(client, monkeypatch):
    """Langfuse owns the live trace; the snapshot owns the history. No Langfuse call needed."""
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.load_trace_view",
                        lambda _id: {"available": True, "total_ms": 100, "steps": []})

    def boom(_tid):
        raise AssertionError("must not hit Langfuse when a snapshot exists")

    monkeypatch.setattr("api.main.trace_read.trace_view", boom)

    payload = client.get("/trace/abc-123").json()

    assert payload["source"] == "stored"
    assert payload["total_ms"] == 100


def test_trace_caches_the_live_view_on_first_read(client, monkeypatch):
    saved = {}
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.load_trace_view", lambda _id: None)
    monkeypatch.setattr("api.main.store.load_meta", lambda _id: ("trace-1", None))
    monkeypatch.setattr("api.main.trace_read.trace_view",
                        lambda tid: {"available": True, "total_ms": 200, "steps": []})
    monkeypatch.setattr("api.main.store.save_trace_view",
                        lambda iid, view: saved.update({"id": iid, "view": view}))

    payload = client.get("/trace/abc-123").json()

    assert payload["source"] == "live"
    assert saved["id"] == "abc-123" and saved["view"]["total_ms"] == 200


def test_unavailable_trace_is_not_cached(client, monkeypatch):
    """Caching a failure would make the outage permanent."""
    monkeypatch.setattr("api.main.clickhouse_available", lambda: True)
    monkeypatch.setattr("api.main.store.load_trace_view", lambda _id: None)
    monkeypatch.setattr("api.main.store.load_meta", lambda _id: (None, None))
    monkeypatch.setattr("api.main.store.save_trace_view",
                        lambda *a: (_ for _ in ()).throw(AssertionError("must not cache")))

    assert client.get("/trace/abc-123").json()["available"] is False


def test_scan_starts_a_background_job(client, monkeypatch):
    seen = {}

    def fake_start(start, end, grain, scope, min_effect, method):
        seen.update({"start": start, "end": end, "method": method})
        return {"job_id": "job-1"}

    monkeypatch.setattr("api.main.dev.start_discover_job", fake_start)

    payload = client.post("/scan", json={"start": "2026-06-01", "end": "2026-06-30"}).json()

    assert payload["job_id"] == "job-1"
    assert seen["start"] == "2026-06-01" and seen["method"] == "isolation_forest"


def test_scan_status_is_polled_by_job_id(client, monkeypatch):
    monkeypatch.setattr("api.main.dev.job_status",
                        lambda jid: {"status": "done", "finished": True, "result": {"count": 3}})

    payload = client.get("/scan/job-1").json()

    assert payload["finished"] is True and payload["result"]["count"] == 3


def test_dashboard_feed_is_scoped_to_the_active_dataset(client, monkeypatch):
    """Regression: /dashboard 500'd on a missing import, and nothing covered the endpoint.

    Also pins the scoping contract — the feed must be limited to the dataset under
    investigation, or dev-era incidents show up while the dashboard points at the streamed slice.
    """
    seen = {}
    monkeypatch.setattr("api.main.store.dataset_bounds", lambda t: ("LO", "HI"))
    monkeypatch.setattr("api.main.store.list_dashboard",
                        lambda limit, since, within: seen.update(limit=limit, within=within) or [])

    payload = client.get("/dashboard?limit=200").json()

    assert payload["count"] == 0
    assert payload["dataset"] == "dev"
    assert seen["limit"] == 200
    assert seen["within"] == ("LO", "HI")
