from datetime import datetime

import pydantic
import pytest

from ingestion.schemas import AdEventRecord, AppRecord


def test_ad_event_record_valid():
    rec = AdEventRecord(
        event_time=datetime(2026, 6, 1, 12, 0, 0),
        app_id="app_1",
        geo_device_id="geo_1",
        advertiser_id="adv_1",
        ad_format="banner",
        is_filled=1,
        is_impression=1,
        is_click=0,
        revenue=1.5,
    )
    assert rec.is_filled == 1
    assert rec.revenue == 1.5


def test_ad_event_record_rejects_non_binary_flag():
    with pytest.raises(pydantic.ValidationError):
        AdEventRecord(
            event_time=datetime(2026, 6, 1, 12, 0, 0),
            app_id="app_1",
            geo_device_id="geo_1",
            advertiser_id="adv_1",
            ad_format="banner",
            is_filled=2,
            is_impression=1,
            is_click=0,
            revenue=1.5,
        )


def test_app_record_valid():
    rec = AppRecord(app_id="app_1", category="gaming", publisher_tier="tier_1")
    assert rec.category == "gaming"
