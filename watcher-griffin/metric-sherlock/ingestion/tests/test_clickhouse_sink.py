from datetime import datetime

import pytest

from ingestion.sinks.clickhouse_sink import COLUMNS_BY_ENTITY, ClickHouseSink


class FakeClient:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.inserts = []

    def insert(self, table, data, column_names):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("transient")
        self.inserts.append((table, data, column_names))


def _row():
    return {
        "event_time": datetime(2026, 7, 6, 0, 0, 0),
        "app_id": "app_1",
        "geo_device_id": "gd_1",
        "advertiser_id": "adv_1",
        "ad_format": "banner",
        "is_filled": 1,
        "is_impression": 1,
        "is_click": 0,
        "revenue": 0.5,
    }


def test_writes_one_batched_insert_in_declared_column_order():
    client = FakeClient()
    ClickHouseSink(client).write("ad_events", [_row()])
    (table, data, column_names), = client.inserts
    assert table == "ad_events"
    assert tuple(column_names) == COLUMNS_BY_ENTITY["ad_events"]
    assert data == [[_row()[c] for c in column_names]]


def test_empty_rows_is_a_noop():
    client = FakeClient()
    ClickHouseSink(client).write("apps", [])
    assert client.inserts == []


def test_retries_transient_failure_then_succeeds():
    client = FakeClient(fail_times=2)
    slept = []
    sink = ClickHouseSink(client, max_retries=3, backoff_seconds=0.1, sleep=slept.append)
    sink.write("apps", [{"app_id": "a", "category": "gaming", "publisher_tier": "tier_1"}])
    assert len(client.inserts) == 1
    assert slept == [0.1, 0.2]  # exponential backoff


def test_raises_after_retries_exhausted():
    client = FakeClient(fail_times=3)
    sink = ClickHouseSink(client, max_retries=3, backoff_seconds=0.1, sleep=lambda s: None)
    with pytest.raises(ConnectionError):
        sink.write("apps", [{"app_id": "a", "category": "gaming", "publisher_tier": "tier_1"}])
