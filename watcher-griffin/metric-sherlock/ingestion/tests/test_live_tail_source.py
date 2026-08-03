import itertools
import os

from ingestion.sources.live_tail_source import LiveTailSource


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _append(path, text):
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(text)


def test_picks_up_existing_rows_then_appended_rows(tmp_path):
    watch_dir = str(tmp_path / "incoming")
    os.makedirs(watch_dir, exist_ok=True)
    data_file = os.path.join(watch_dir, "apps.csv")
    _write(data_file, "app_id,category,publisher_tier\napp_1,gaming,tier_1\napp_2,social,tier_2\n")

    source = LiveTailSource(watch_dir, poll_interval_seconds=0.01)
    first_two = list(itertools.islice(source.records(), 2))
    assert first_two == [
        {"app_id": "app_1", "category": "gaming", "publisher_tier": "tier_1"},
        {"app_id": "app_2", "category": "social", "publisher_tier": "tier_2"},
    ]

    _append(data_file, "app_3,news,tier_3\n")
    next_one = list(itertools.islice(source.records(), 1))
    assert next_one == [{"app_id": "app_3", "category": "news", "publisher_tier": "tier_3"}]


def test_offset_state_persists_across_restart(tmp_path):
    watch_dir = str(tmp_path / "incoming")
    os.makedirs(watch_dir, exist_ok=True)
    data_file = os.path.join(watch_dir, "apps.csv")
    _write(data_file, "app_id,category,publisher_tier\napp_1,gaming,tier_1\n")

    source1 = LiveTailSource(watch_dir, poll_interval_seconds=0.01)
    seen_first_run = list(itertools.islice(source1.records(), 1))
    assert seen_first_run == [{"app_id": "app_1", "category": "gaming", "publisher_tier": "tier_1"}]

    # Simulate a restart: append new rows, then create a brand-new source
    # instance pointed at the same watch_dir/state file.
    _append(data_file, "app_2,social,tier_2\n")
    source2 = LiveTailSource(watch_dir, poll_interval_seconds=0.01)
    seen_second_run = list(itertools.islice(source2.records(), 1))

    assert seen_second_run == [{"app_id": "app_2", "category": "social", "publisher_tier": "tier_2"}]
