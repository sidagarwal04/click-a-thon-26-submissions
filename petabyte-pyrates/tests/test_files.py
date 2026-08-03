from pathlib import Path

from inmobi_ingest.files import is_lfs_pointer, read_dimension_rows, resolve_csv_path


def test_is_lfs_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "apps.csv"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n",
        encoding="utf-8",
    )
    real = tmp_path / "real.csv"
    real.write_text("app_id,category,publisher_tier\napp_1,games,tier_1\n", encoding="utf-8")

    assert is_lfs_pointer(pointer) is True
    assert is_lfs_pointer(real) is False


def test_read_dimension_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "apps.csv"
    csv_path.write_text(
        "app_id,category,publisher_tier\napp_1,games,tier_1\n",
        encoding="utf-8",
    )
    rows = read_dimension_rows(csv_path, ["app_id", "category", "publisher_tier"])
    assert rows == [("app_1", "games", "tier_1")]


def test_resolve_csv_path_downloads_lfs_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "advertisers.csv"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:5b3e6ba0181bfcb04645cc631c05a117a6454178bbdf141d6c2c0373a15e659e\n"
        "size 10533\n",
        encoding="utf-8",
    )
    resolved = resolve_csv_path(tmp_path, "advertisers.csv")
    header = resolved.read_text(encoding="utf-8").splitlines()[0]
    assert header == "advertiser_id,vertical,campaign_type"
