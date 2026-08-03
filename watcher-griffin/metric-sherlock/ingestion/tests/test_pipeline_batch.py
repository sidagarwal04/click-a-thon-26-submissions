from datetime import datetime
from typing import Any, Dict, Iterator, List

from ingestion.config import load_config
from ingestion.pipeline import IngestionPipeline
from ingestion.sinks import Sink
from ingestion.sources import Source


class FakeSource(Source):
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows

    def records(self) -> Iterator[Dict[str, Any]]:
        yield from self.rows


class FakeSink(Sink):
    def __init__(self):
        self.calls = []

    def write(self, entity: str, rows: List[Dict[str, Any]]) -> None:
        self.calls.append((entity, rows))

    def all_rows(self):
        return [row for _, rows in self.calls for row in rows]


def test_pipeline_splits_valid_and_invalid_rows():
    rows = [
        {
            "event_time": "2026-06-01 12:00:00",
            "app_id": "app_1",
            "geo_device_id": "geo_1",
            "advertiser_id": "adv_1",
            "ad_format": "banner",
            "is_filled": 1,
            "is_impression": 1,
            "is_click": 0,
            "revenue": 1.0,
        },
        {
            # bad region-style enum on ad_format + funnel violation
            "event_time": "2026-06-01 13:00:00",
            "app_id": "app_2",
            "geo_device_id": "geo_2",
            "advertiser_id": "",
            "ad_format": "popup",
            "is_filled": 0,
            "is_impression": 1,
            "is_click": 1,
            "revenue": 3.0,
        },
    ]
    source = FakeSource(rows)
    valid_sink = FakeSink()
    dead_sink = FakeSink()
    cfg = load_config()

    pipeline = IngestionPipeline(source, valid_sink, dead_sink, "ad_events", cfg)
    stats = pipeline.run()

    assert stats["accepted"] == 1
    assert stats["rejected"] == 1
    assert stats["skipped"] == 0
    assert stats["extra_fields_seen"] == []
    assert len(valid_sink.all_rows()) == 1
    assert valid_sink.all_rows()[0]["app_id"] == "app_1"

    rejected = dead_sink.all_rows()
    assert len(rejected) == 1
    assert rejected[0]["record"]["app_id"] == "app_2"
    assert any("ad_format" in e for e in rejected[0]["errors"])
    assert any("funnel violated" in e for e in rejected[0]["errors"])


def test_pipeline_skips_blank_rows_and_tracks_extra_fields():
    rows = [
        {
            "event_time": "2026-06-01 12:00:00",
            "app_id": "app_1",
            "geo_device_id": "geo_1",
            "advertiser_id": "adv_1",
            "ad_format": "banner",
            "is_filled": 1,
            "is_impression": 1,
            "is_click": 0,
            "revenue": 1.0,
            "session_id": "sess_1",  # unexpected extra column
        },
        {  # completely blank row -- noise, not a violation
            "event_time": "",
            "app_id": "",
            "geo_device_id": "",
            "advertiser_id": "",
            "ad_format": "",
            "is_filled": "",
            "is_impression": "",
            "is_click": "",
            "revenue": "",
        },
    ]
    source = FakeSource(rows)
    valid_sink = FakeSink()
    dead_sink = FakeSink()
    cfg = load_config()

    pipeline = IngestionPipeline(source, valid_sink, dead_sink, "ad_events", cfg)
    stats = pipeline.run()

    assert stats["accepted"] == 1
    assert stats["rejected"] == 0
    assert stats["skipped"] == 1
    assert stats["extra_fields_seen"] == ["session_id"]
    assert dead_sink.all_rows() == []


def test_accepted_payloads_are_python_mode_for_sinks():
    """Sinks receive real datetime/float objects; JsonlSink stringifies at
    write time and ClickHouseSink inserts them natively."""
    rows = [
        {
            "event_time": "2026-06-01 12:00:00",
            "app_id": "app_1",
            "geo_device_id": "geo_1",
            "advertiser_id": "adv_1",
            "ad_format": "banner",
            "is_filled": 1,
            "is_impression": 1,
            "is_click": 0,
            "revenue": 1.0,
        }
    ]
    valid_sink = FakeSink()
    pipeline = IngestionPipeline(FakeSource(rows), valid_sink, FakeSink(), "ad_events", load_config())
    pipeline.run()
    payload = valid_sink.all_rows()[0]
    assert isinstance(payload["event_time"], datetime)
    assert isinstance(payload["revenue"], float)
