from datetime import datetime

from ingestion.transformers import (
    MALFORMED_LINE_KEY,
    normalize_ad_event,
    normalize_app,
    normalize_geo_device,
)


def _valid_raw():
    return {
        "event_time": "2026-06-01 12:00:00",
        "app_id": "app_1",
        "geo_device_id": "geo_1",
        "advertiser_id": "adv_1",
        "ad_format": "banner",
        "is_filled": "1",
        "is_impression": "true",
        "is_click": "0",
        "revenue": "2.50",
    }


def test_normalize_coerces_string_flags_and_whitespace():
    row, errors, extra = normalize_ad_event(_valid_raw())
    assert errors == []
    assert extra == []
    assert row["app_id"] == "app_1"
    assert row["ad_format"] == "banner"
    assert row["is_filled"] == 1
    assert row["is_impression"] == 1
    assert row["is_click"] == 0
    assert row["revenue"] == 2.50
    assert row["event_time"] == datetime(2026, 6, 1, 12, 0, 0)


def test_normalize_epoch_millis_event_time():
    raw = _valid_raw()
    raw["event_time"] = 1748779200000  # ms epoch
    row, errors, extra = normalize_ad_event(raw)
    assert errors == []
    assert isinstance(row["event_time"], datetime)


def test_normalize_unparsable_event_time_reports_error():
    raw = _valid_raw()
    raw["event_time"] = "not-a-date"
    row, errors, extra = normalize_ad_event(raw)
    assert any("event_time" in e for e in errors)


def test_missing_flag_is_rejected_not_defaulted():
    """A null/blank funnel flag must be surfaced, never silently coerced to 0."""
    raw = _valid_raw()
    raw["is_filled"] = ""
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_filled"] is None
    assert any("is_filled" in e for e in errors)


def test_null_token_flag_is_rejected():
    raw = _valid_raw()
    raw["is_click"] = "null"
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_click"] is None
    assert any("is_click" in e for e in errors)


def test_null_token_revenue_is_rejected():
    raw = _valid_raw()
    raw["revenue"] = "N/A"
    row, errors, extra = normalize_ad_event(raw)
    assert row["revenue"] is None
    assert any("revenue" in e for e in errors)


def test_control_characters_and_whitespace_stripped():
    raw = _valid_raw()
    raw["app_id"] = "\x00 app_1 \x7f"
    row, errors, extra = normalize_ad_event(raw)
    assert row["app_id"] == "app_1"


def test_extra_unexpected_field_is_selected_out_and_reported():
    raw = _valid_raw()
    raw["session_id"] = "sess_123"
    row, errors, extra = normalize_ad_event(raw)
    assert errors == []
    assert "session_id" not in row
    assert extra == ["session_id"]


def test_noisy_header_casing_is_still_recognized():
    raw = {
        "Event_Time": "2026-06-01 12:00:00",
        "AppId": "app_1",
        "GeoDeviceID": "geo_1",
        "advertiser-id": "adv_1",
        "Ad Format": "banner",
        "IsFilled": "1",
        "isImpression": "1",
        "is_click": "0",
        "Revenue": "1.0",
    }
    row, errors, extra = normalize_ad_event(raw)
    assert errors == []
    assert extra == []
    assert row["app_id"] == "app_1"
    assert row["geo_device_id"] == "geo_1"
    assert row["advertiser_id"] == "adv_1"
    assert row["ad_format"] == "banner"
    assert row["is_filled"] == 1
    assert row["is_impression"] == 1


def test_blank_row_is_skipped_not_rejected():
    raw = {
        "event_time": "",
        "app_id": None,
        "geo_device_id": "null",
        "advertiser_id": "",
        "ad_format": "N/A",
        "is_filled": "",
        "is_impression": "",
        "is_click": "",
        "revenue": "",
    }
    row, errors, extra = normalize_ad_event(raw)
    assert row is None
    assert errors == []


def test_duplicate_header_row_is_skipped():
    raw = {"app_id": "app_id", "category": "category", "publisher_tier": "publisher_tier"}
    row, errors, extra = normalize_app(raw)
    assert row is None
    assert errors == []


def test_region_na_literal_survives_null_collapsing():
    """A literal 'NA' region must NOT be collapsed to null-token empty --
    validators.py needs to see it as-is to give the NA/NAM-typo hint."""
    raw = {
        "geo_device_id": "geo_1",
        "region": "na",
        "country": "US",
        "device_model": "x",
        "os_version": "1",
    }
    row, errors, extra = normalize_geo_device(raw)
    assert errors == []
    assert row["region"] == "NA"


def test_malformed_line_sentinel_is_rejected():
    raw = {MALFORMED_LINE_KEY: "app_1,gaming"}  # missing a column
    row, errors, extra = normalize_app(raw)
    assert row is None
    assert len(errors) == 1
    assert "malformed line" in errors[0]


def test_fractional_flag_string_is_rejected_not_truncated():
    """'0.5' must NOT silently become 0 -- that is fabricated data."""
    raw = _valid_raw()
    raw["is_click"] = "0.5"
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_click"] is None
    assert any("is_click" in e for e in errors)


def test_fractional_flag_float_is_rejected_not_truncated():
    raw = _valid_raw()
    raw["is_impression"] = 1.9
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_impression"] is None
    assert any("is_impression" in e for e in errors)


def test_integral_float_flag_still_accepted():
    raw = _valid_raw()
    raw["is_filled"] = 1.0
    row, errors, extra = normalize_ad_event(raw)
    assert errors == []
    assert row["is_filled"] == 1
