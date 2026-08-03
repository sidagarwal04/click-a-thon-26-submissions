"""JAL-84: session listing and deletion, with the store stubbed.

These endpoints are operational rather than analytical - they exist so a demo run starts from
a clean slate and so an earlier conversation can be replayed. The contract worth pinning is
that deleting conversations never touches the investigations, which are the evidence record.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sessions(monkeypatch):
    """Two sessions, one with turns, plus a matching investigation."""
    rows = [
        {"context_id": "ctx-1", "title": "Revenue drop Jun 23",
         "created_at": "2026-06-23T10:00:00", "updated_at": "2026-06-23T10:05:00"},
        {"context_id": "ctx-2", "title": "",
         "created_at": "2026-06-24T09:00:00", "updated_at": "2026-06-24T09:01:00"},
    ]
    turns = {
        "ctx-1": [{"role": "user", "message": "why did revenue drop?", "created_at": "t1"},
                  {"role": "assistant", "message": "Android 15.", "created_at": "t2"}],
        "ctx-2": [],
    }
    investigations = [
        {"investigation_id": "inv-a", "session_id": "ctx-1"},
        {"investigation_id": "inv-b", "session_id": "other"},
    ]
    deleted = {"single": [], "all": 0}

    def fake_delete(context_id):
        if context_id not in turns:
            return False
        deleted["single"].append(context_id)
        return True

    def fake_delete_all():
        deleted["all"] = len(rows)
        return len(rows)

    monkeypatch.setattr("api.main.store.list_sessions", lambda limit: rows)
    monkeypatch.setattr("api.main.store.get_turns", lambda cid, n: turns.get(cid, []))
    monkeypatch.setattr("api.main.store.list_investigations", lambda n: investigations)
    monkeypatch.setattr("api.main.store.delete_session", fake_delete)
    monkeypatch.setattr("api.main.store.delete_all_sessions", fake_delete_all)
    return deleted


# ---- listing ---------------------------------------------------------------

def test_list_returns_sessions_with_history(client, sessions):
    payload = client.get("/chat/sessions").json()

    assert payload["count"] == 2
    first = payload["sessions"][0]
    assert first["context_id"] == "ctx-1"
    assert [t["role"] for t in first["history"]] == ["user", "assistant"]


def test_list_includes_a_session_with_no_turns(client, sessions):
    """An empty conversation is still a session, not an error."""
    payload = client.get("/chat/sessions").json()

    assert payload["sessions"][1]["history"] == []


def test_list_forwards_limits(client, monkeypatch):
    seen = {}

    def fake_list(limit):
        seen["limit"] = limit
        return [{"context_id": "c"}]

    def fake_turns(cid, n):
        seen["turns"] = n
        return []

    monkeypatch.setattr("api.main.store.list_sessions", fake_list)
    monkeypatch.setattr("api.main.store.get_turns", fake_turns)

    client.get("/chat/sessions?limit=5&turns=3")

    assert seen == {"limit": 5, "turns": 3}


def test_list_empty_is_not_an_error(client, monkeypatch):
    monkeypatch.setattr("api.main.store.list_sessions", lambda limit: [])

    res = client.get("/chat/sessions")

    assert res.status_code == 200
    assert res.json() == {"count": 0, "sessions": []}


# ---- single session --------------------------------------------------------

def test_single_session_links_its_investigations(client, sessions):
    """This is what makes a replay useful: each id resolves via GET /bundle/{id}."""
    payload = client.get("/chat/sessions/ctx-1").json()

    assert payload["turns"] == 2
    assert payload["investigations"] == ["inv-a"]


def test_single_session_excludes_other_sessions_investigations(client, sessions):
    payload = client.get("/chat/sessions/ctx-1").json()

    assert "inv-b" not in payload["investigations"]


def test_unknown_session_is_404(client, sessions):
    res = client.get("/chat/sessions/nope")

    assert res.status_code == 404
    assert "nope" in res.json()["detail"]


# ---- deletion --------------------------------------------------------------

def test_delete_one_session(client, sessions):
    res = client.delete("/chat/sessions/ctx-1")

    assert res.status_code == 200
    assert res.json() == {"context_id": "ctx-1", "deleted": True}
    assert sessions["single"] == ["ctx-1"]


def test_delete_unknown_session_is_404(client, sessions):
    res = client.delete("/chat/sessions/nope")

    assert res.status_code == 404
    assert sessions["single"] == []


def test_delete_all_reports_the_count(client, sessions):
    res = client.delete("/chat/sessions")

    assert res.status_code == 200
    assert res.json() == {"deleted": 2}


def test_clearing_sessions_never_touches_investigations(client, sessions, monkeypatch):
    """Investigations are the evidence record. Losing them would break GET /bundle/{id}
    for anything already submitted."""
    touched = []
    monkeypatch.setattr("api.main.store.save_bundle",
                        lambda *a, **kw: touched.append("save"))

    client.delete("/chat/sessions")

    assert touched == []
    assert sessions["all"] == 2
