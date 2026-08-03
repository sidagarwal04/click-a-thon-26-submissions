"""Dataset switching: dev tables vs the sealed unseen slice.

The switch has to resolve at CALL time. Module-level constants captured at import were the
original bug class here — a mid-process switch would silently keep querying the old tables.
"""
import pytest

import config as cfg


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv(cfg._TARGET_ENV, raising=False)
    monkeypatch.delenv(cfg._HISTORY_ENV, raising=False)


def test_defaults_to_dev_for_both_roles():
    assert cfg.dataset_name("target") == "dev"
    assert cfg.dataset_name("history") == "dev"
    assert cfg.target_hourly() == "hourly_summary"
    assert cfg.baseline_hourly() == "hourly_summary"


def test_env_switches_the_target_only(monkeypatch):
    """Production run: investigate the unseen slice, keep baselines on dev history."""
    monkeypatch.setenv(cfg._TARGET_ENV, "unseen")

    assert cfg.target_hourly() == "hourly_summary_unseen"
    assert cfg.baseline_hourly() == "hourly_summary"


def test_history_is_independently_switchable(monkeypatch):
    monkeypatch.setenv(cfg._HISTORY_ENV, "unseen")

    assert cfg.baseline_hourly() == "hourly_summary_unseen"
    assert cfg.target_hourly() == "hourly_summary"


def test_tables_map_covers_every_role_the_loader_needs(monkeypatch):
    monkeypatch.setenv(cfg._TARGET_ENV, "unseen")
    t = cfg.tables("target")

    assert t["events"] == "ad_events_unseen"
    assert t["enriched"] == "events_full_unseen"
    assert {"apps", "advertisers", "geo_device"} <= set(t)


def test_unknown_dataset_fails_loudly(monkeypatch):
    """Silently falling back to dev would investigate the wrong data and report it as real."""
    monkeypatch.setenv(cfg._TARGET_ENV, "nope")

    with pytest.raises(ValueError, match="unknown dataset"):
        cfg.tables("target")


def test_dev_and_unseen_share_no_table_names():
    dev, unseen = cfg.config()["datasets"]["dev"], cfg.config()["datasets"]["unseen"]

    assert set(dev.values()).isdisjoint(unseen.values())
