"""ClickHouseStore must serialize client access across FastAPI worker threads."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.store import ClickHouseStore  # noqa: E402


class _FakeResult:
    def __init__(self, rows=None, names=None):
        self.result_rows = rows or [["ok"]]
        self.column_names = names or ["v"]


def _make_store_with_tracking_client() -> tuple[ClickHouseStore, list[str]]:
    """Build a ClickHouseStore whose client records overlapping calls."""
    active = 0
    max_active = 0
    lock = threading.Lock()
    events: list[str] = []

    def _query(*_a, **_k):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            events.append("enter")
        time.sleep(0.05)
        with lock:
            active -= 1
            events.append("exit")
        return _FakeResult([["1"]], ["v"])

    client = MagicMock()
    client.query.side_effect = _query
    client.command.return_value = None
    client.database = "atlys"

    fake_ch = SimpleNamespace(get_client=MagicMock(return_value=client))
    with patch.dict(sys.modules, {"clickhouse_connect": fake_ch}):
        store = ClickHouseStore(host="localhost", user="default", database="atlys", retries=1)
    store._max_active = lambda: max_active  # type: ignore[attr-defined]
    return store, events


def test_clickhouse_store_serializes_concurrent_queries():
    store, _events = _make_store_with_tracking_client()
    errors: list[BaseException] = []

    def worker():
        try:
            store.query_rows("SELECT 1")
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert store._max_active() == 1  # type: ignore[attr-defined]
