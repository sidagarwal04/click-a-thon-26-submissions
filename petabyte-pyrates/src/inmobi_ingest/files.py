"""Resolve InMobi data files, including Git LFS pointer fallbacks."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

LFS_POINTER_PREFIX = "version https://git-lfs.github.com/spec/v1"
DEFAULT_LFS_MEDIA_BASE = (
    "https://media.githubusercontent.com/media/sidagarwal04/click-a-thon-2026/main/InMobi/data"
)

DIMENSION_FILES = {
    "apps": ("apps.csv", ["app_id", "category", "publisher_tier"]),
    "advertisers": ("advertisers.csv", ["advertiser_id", "vertical", "campaign_type"]),
    "geo_device": (
        "geo_device.csv",
        ["geo_device_id", "region", "country", "device_model", "os_version"],
    ),
}


def is_lfs_pointer(path: Path) -> bool:
    if not path.is_file():
        return False
    first_line = path.read_text(encoding="utf-8").splitlines()[:1]
    return bool(first_line and first_line[0].startswith(LFS_POINTER_PREFIX))


def resolve_csv_path(
    data_dir: Path,
    filename: str,
    *,
    lfs_media_base: str = DEFAULT_LFS_MEDIA_BASE,
) -> Path:
    """Return a readable CSV path, downloading LFS-backed files when needed."""
    local_path = data_dir / filename
    if local_path.is_file() and not is_lfs_pointer(local_path):
        return local_path

    url = f"{lfs_media_base.rstrip('/')}/{filename}"
    try:
        with urlopen(url, timeout=60) as response:
            payload = response.read()
    except URLError as exc:
        if local_path.is_file():
            raise RuntimeError(
                f"{local_path} is a Git LFS pointer and could not be fetched from {url}: {exc}"
            ) from exc
        raise FileNotFoundError(f"Missing data file: {local_path}") from exc

    temp_file = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f"inmobi_{filename.replace('.', '_')}_",
        suffix=".csv",
        delete=False,
    )
    temp_file.write(payload)
    temp_file.close()
    return Path(temp_file.name)


def ad_events_parquet_path(data_dir: Path) -> Path:
    path = data_dir / "ad_events.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing parquet file: {path}")
    return path


def read_dimension_rows(path: Path, expected_columns: list[str]) -> list[tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"Unexpected columns in {path.name}: {reader.fieldnames!r}; "
                f"expected {expected_columns!r}"
            )
        return [tuple(row[column] for column in expected_columns) for row in reader]


def rows_from_csv_source(
    data_dir: Path,
    table: str,
    *,
    lfs_media_base: str = DEFAULT_LFS_MEDIA_BASE,
) -> tuple[Path, list[tuple[str, ...]]]:
    filename, columns = DIMENSION_FILES[table]
    path = resolve_csv_path(data_dir, filename, lfs_media_base=lfs_media_base)
    return path, read_dimension_rows(path, columns)


def sniff_csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)
