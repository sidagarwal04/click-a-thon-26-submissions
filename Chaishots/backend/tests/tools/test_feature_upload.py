from io import BytesIO
from pathlib import Path

import pytest

from app.tools.feature_source import InvalidFeatureKeyError
from app.tools.feature_upload import (
    EmptyUploadedFileError,
    UploadedFileTooLargeError,
    store_feature_upload,
)


def _store(
    root: Path,
    *,
    feature: str = "01_checkout",
    spec: bytes = b"# Checkout",
    events: bytes = b'{"event":"shown"}\n',
    max_spec_bytes: int = 1024,
    max_event_bytes: int = 1024,
) -> Path:
    return store_feature_upload(
        root,
        feature,
        spec_stream=BytesIO(spec),
        events_stream=BytesIO(events),
        max_spec_bytes=max_spec_bytes,
        max_event_bytes=max_event_bytes,
    )


def test_store_feature_upload_creates_required_folder(tmp_path: Path) -> None:
    folder = _store(tmp_path)

    assert folder == tmp_path / "01_checkout"
    assert (folder / "spec.md").read_bytes() == b"# Checkout"
    assert (folder / "events.ndjson").read_bytes() == b'{"event":"shown"}\n'
    assert sorted(path.name for path in folder.iterdir()) == [
        "events.ndjson",
        "spec.md",
    ]


def test_store_feature_upload_replaces_existing_feature_files(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "01_checkout"
    existing.mkdir()
    (existing / "spec.md").write_text("original", encoding="utf-8")

    folder = _store(tmp_path)

    assert folder == existing
    assert (existing / "spec.md").read_bytes() == b"# Checkout"
    assert (existing / "events.ndjson").read_bytes() == b'{"event":"shown"}\n'


@pytest.mark.parametrize("feature", ["../escape", "nested/feature", "has space"])
def test_store_feature_upload_rejects_unsafe_keys(
    tmp_path: Path,
    feature: str,
) -> None:
    with pytest.raises(InvalidFeatureKeyError):
        _store(tmp_path, feature=feature)


def test_store_feature_upload_uses_canonical_names(
    tmp_path: Path,
) -> None:
    folder = _store(tmp_path)

    assert (folder / "spec.md").read_bytes() == b"# Checkout"
    assert (folder / "events.ndjson").read_bytes() == b'{"event":"shown"}\n'
    assert sorted(path.name for path in folder.iterdir()) == [
        "events.ndjson",
        "spec.md",
    ]


@pytest.mark.parametrize(
    ("spec", "events", "error"),
    [
        (b"", b"{}\n", EmptyUploadedFileError),
        (b"ok", b"", EmptyUploadedFileError),
        (b"too big", b"{}\n", UploadedFileTooLargeError),
        (b"ok", b'{"large":"event"}\n', UploadedFileTooLargeError),
    ],
)
def test_failed_upload_removes_partial_folder(
    tmp_path: Path,
    spec: bytes,
    events: bytes,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        _store(
            tmp_path,
            spec=spec,
            events=events,
            max_spec_bytes=3,
            max_event_bytes=3,
        )

    assert not (tmp_path / "01_checkout").exists()


def test_failed_replacement_preserves_existing_feature_files(tmp_path: Path) -> None:
    existing = tmp_path / "01_checkout"
    existing.mkdir()
    (existing / "spec.md").write_bytes(b"original spec")
    (existing / "events.ndjson").write_bytes(b'{"event":"original"}\n')

    with pytest.raises(UploadedFileTooLargeError):
        _store(tmp_path, events=b"too large", max_event_bytes=3)

    assert (existing / "spec.md").read_bytes() == b"original spec"
    assert (existing / "events.ndjson").read_bytes() == b'{"event":"original"}\n'
