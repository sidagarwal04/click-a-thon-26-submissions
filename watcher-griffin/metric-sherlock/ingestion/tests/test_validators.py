from ingestion.config import load_config
from ingestion.validators import validate_ad_event, validate_geo_device

cfg = load_config()


def _base_event(**overrides):
    row = {
        "app_id": "app_1",
        "geo_device_id": "geo_1",
        "ad_format": "banner",
        "is_filled": 1,
        "is_impression": 1,
        "is_click": 0,
        "revenue": 1.0,
        "advertiser_id": "adv_1",
    }
    row.update(overrides)
    return row


def test_valid_event_has_no_violations():
    assert validate_ad_event(_base_event(), cfg) == []


def test_funnel_violation_detected():
    errors = validate_ad_event(_base_event(is_impression=0, is_click=1), cfg)
    assert any("funnel violated" in e for e in errors)


def test_revenue_without_impression_is_rejected():
    errors = validate_ad_event(_base_event(is_impression=0, revenue=5.0, advertiser_id="adv_1", is_filled=1), cfg)
    assert any("revenue must be 0" in e for e in errors)


def test_advertiser_required_when_filled():
    errors = validate_ad_event(_base_event(advertiser_id=""), cfg)
    assert any("must be non-empty" in e for e in errors)


def test_advertiser_must_be_empty_when_unfilled():
    errors = validate_ad_event(
        _base_event(is_filled=0, is_impression=0, is_click=0, revenue=0, advertiser_id="adv_1"), cfg
    )
    assert any("must be empty" in e for e in errors)


def test_missing_app_id_rejected():
    errors = validate_ad_event(_base_event(app_id=""), cfg)
    assert any("app_id" in e for e in errors)


def test_missing_geo_device_id_rejected():
    errors = validate_ad_event(_base_event(geo_device_id=""), cfg)
    assert any("geo_device_id" in e for e in errors)


def test_bad_ad_format_rejected():
    errors = validate_ad_event(_base_event(ad_format="popup"), cfg)
    assert any("ad_format" in e for e in errors)


def test_region_na_gets_explicit_hint():
    errors = validate_geo_device(
        {"geo_device_id": "geo_1", "region": "NA", "country": "US", "device_model": "x", "os_version": "1"},
        cfg,
    )
    assert any("NAM" in e for e in errors)


def test_region_valid():
    errors = validate_geo_device(
        {"geo_device_id": "geo_1", "region": "NAM", "country": "US", "device_model": "x", "os_version": "1"},
        cfg,
    )
    assert errors == []
