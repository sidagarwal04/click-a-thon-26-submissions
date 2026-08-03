from pathlib import Path

import pytest

from app.tools.feature_source import (
    FeatureFileError,
    FeatureFileTooLargeError,
    FeatureNotFoundError,
    FeatureSourceSecurityError,
    InvalidFeatureKeyError,
    read_feature_files,
    resolve_feature_folder,
)


def _write_feature(root: Path, feature: str = "01_checkout") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    folder = root / feature
    folder.mkdir()
    (folder / "spec.md").write_text("# Express checkout", encoding="utf-8")
    (folder / "events.ndjson").write_text('{"event":"shown"}\n', encoding="utf-8")
    return folder


def test_read_feature_files_returns_bounded_spec_and_event_path(
    tmp_path: Path,
) -> None:
    folder = _write_feature(tmp_path)

    result = read_feature_files(tmp_path, "01_checkout")

    assert result.feature == "01_checkout"
    assert result.spec == "# Express checkout"
    assert result.events_path == (folder / "events.ndjson").resolve()


@pytest.mark.parametrize(
    "feature_key",
    ["../secret", "nested/feature", ".", "", "has space", "feature.json"],
)
def test_rejects_unsafe_feature_keys(tmp_path: Path, feature_key: str) -> None:
    with pytest.raises(InvalidFeatureKeyError):
        resolve_feature_folder(tmp_path, feature_key)


def test_missing_feature_folder_has_domain_error(tmp_path: Path) -> None:
    with pytest.raises(FeatureNotFoundError, match="not found"):
        resolve_feature_folder(tmp_path, "missing")


@pytest.mark.parametrize("missing_name", ["spec.md", "events.ndjson"])
def test_requires_both_input_files(tmp_path: Path, missing_name: str) -> None:
    folder = _write_feature(tmp_path)
    (folder / missing_name).unlink()

    with pytest.raises(FeatureFileError, match=missing_name):
        read_feature_files(tmp_path, "01_checkout")


def test_spec_read_is_byte_bounded(tmp_path: Path) -> None:
    folder = _write_feature(tmp_path)
    (folder / "spec.md").write_bytes(b"12345")

    with pytest.raises(FeatureFileTooLargeError, match="4-byte"):
        read_feature_files(tmp_path, "01_checkout", max_spec_bytes=4)


def test_spec_must_be_utf8(tmp_path: Path) -> None:
    folder = _write_feature(tmp_path)
    (folder / "spec.md").write_bytes(b"\xff")

    with pytest.raises(FeatureFileError, match="UTF-8"):
        read_feature_files(tmp_path, "01_checkout")


def test_rejects_feature_folder_symlink_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "features"
    outside = tmp_path / "outside"
    root.mkdir()
    _write_feature(outside)
    (root / "escaped").symlink_to(outside / "01_checkout", target_is_directory=True)

    with pytest.raises(FeatureSourceSecurityError, match="outside"):
        resolve_feature_folder(root, "escaped")


def test_rejects_required_file_symlink_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "features"
    root.mkdir()
    folder = _write_feature(root)
    external_spec = tmp_path / "external.md"
    external_spec.write_text("secret", encoding="utf-8")
    (folder / "spec.md").unlink()
    (folder / "spec.md").symlink_to(external_spec)

    with pytest.raises(FeatureSourceSecurityError, match="outside"):
        read_feature_files(root, "01_checkout")
