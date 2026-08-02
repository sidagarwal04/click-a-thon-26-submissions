import os

import pytest

from ingestion.detect import EntityDetectionError, detect_entity_for_file, plan_path


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_detects_by_filename_stem(tmp_path):
    p = str(tmp_path / "apps.txt")
    _write(p, "app_id,category,publisher_tier\n")
    assert detect_entity_for_file(p) == "apps"


def test_detects_ad_events_parquet_by_filename(tmp_path):
    p = str(tmp_path / "ad_events_v2.parquet")
    _write(p, "")  # filename wins; content never read
    assert detect_entity_for_file(p) == "ad_events"


def test_detects_by_csv_header_when_filename_unhelpful(tmp_path):
    p = str(tmp_path / "drop_2026_07.csv")
    _write(p, "GeoDeviceID,Region,Country,Device Model,OS Version\n")
    assert detect_entity_for_file(p) == "geo_device"


def test_unrecognizable_columns_raise_with_columns_listed(tmp_path):
    p = str(tmp_path / "mystery.csv")
    _write(p, "foo,bar\n")
    with pytest.raises(EntityDetectionError) as exc:
        detect_entity_for_file(p)
    assert "foo" in str(exc.value)


def test_plan_path_orders_dimensions_before_facts(tmp_path):
    _write(str(tmp_path / "ad_events.csv"), "event_time,app_id,geo_device_id,advertiser_id,ad_format,is_filled,is_impression,is_click,revenue\n")
    _write(str(tmp_path / "apps.txt"), "app_id,category,publisher_tier\n")
    _write(str(tmp_path / "geo_device.txt"), "geo_device_id,region,country,device_model,os_version\n")
    _write(str(tmp_path / "advertisers.txt"), "advertiser_id,vertical,campaign_type\n")
    _write(str(tmp_path / "notes.md"), "not data\n")
    plan = plan_path(str(tmp_path))
    entities = [e for e, _ in plan]
    assert entities == ["apps", "advertisers", "geo_device", "ad_events"]


def test_plan_path_single_file(tmp_path):
    p = str(tmp_path / "advertisers.txt")
    _write(p, "advertiser_id,vertical,campaign_type\n")
    assert plan_path(p) == [("advertisers", p)]


def test_plan_path_duplicate_entity_raises(tmp_path):
    _write(str(tmp_path / "apps.txt"), "app_id,category,publisher_tier\n")
    _write(str(tmp_path / "apps_old.csv"), "app_id,category,publisher_tier\n")
    with pytest.raises(EntityDetectionError):
        plan_path(str(tmp_path))


def test_plan_path_empty_dir_raises(tmp_path):
    with pytest.raises(EntityDetectionError):
        plan_path(str(tmp_path))


def test_invalid_parquet_file_raises_entity_detection_error(tmp_path):
    """Test that a non-parquet file with .parquet extension raises EntityDetectionError, not ArrowInvalid."""
    p = str(tmp_path / "mystery.parquet")
    _write(p, "not parquet")
    with pytest.raises(EntityDetectionError):
        detect_entity_for_file(p)


def test_plan_path_skips_invalid_parquet_with_valid_csv(tmp_path):
    """Test that plan_path skips invalid parquet file and processes valid CSV successfully."""
    _write(str(tmp_path / "mystery.parquet"), "not parquet")
    _write(str(tmp_path / "apps.txt"), "app_id,category,publisher_tier\n")
    plan = plan_path(str(tmp_path))
    assert len(plan) == 1
    assert plan[0][0] == "apps"
