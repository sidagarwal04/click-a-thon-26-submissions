from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from app.tools.feature_source import (
    EVENTS_FILENAME,
    SPEC_FILENAME,
    FeatureRootError,
    validate_feature_key,
)

DEFAULT_MAX_EVENT_FILE_BYTES = 512 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


class FeatureUploadError(Exception):
    """Base error for storing an uploaded feature folder."""


class UploadedFileTooLargeError(FeatureUploadError):
    """Raised when an uploaded file exceeds its configured byte bound."""


class EmptyUploadedFileError(FeatureUploadError):
    """Raised when an uploaded required file is empty."""


class FeatureUploadStorageError(FeatureUploadError):
    """Raised when the upload cannot be written durably."""


def _resolved_root(features_root: str | Path) -> Path:
    root = Path(features_root)
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise FeatureRootError(f"Feature root does not exist: {root}") from exc
    if not resolved.is_dir():
        raise FeatureRootError(f"Feature root is not a directory: {root}")
    return resolved


def _copy_bounded(
    source: BinaryIO,
    destination: Path,
    *,
    label: str,
    max_bytes: int,
) -> int:
    total = 0
    try:
        source.seek(0)
        with destination.open("xb") as output:
            while chunk := source.read(UPLOAD_CHUNK_BYTES):
                total += len(chunk)
                if total > max_bytes:
                    raise UploadedFileTooLargeError(
                        f"{label} exceeds the {max_bytes}-byte upload limit."
                    )
                output.write(chunk)
    except FeatureUploadError:
        raise
    except OSError as exc:
        raise FeatureUploadStorageError(f"Could not store uploaded {label}.") from exc

    if total == 0:
        raise EmptyUploadedFileError(f"Uploaded {label} must not be empty.")
    return total


def _clean_failed_upload(folder: Path, *, remove_folder: bool) -> None:
    for name in (
        f".{SPEC_FILENAME}.upload",
        f".{EVENTS_FILENAME}.upload",
    ):
        try:
            (folder / name).unlink(missing_ok=True)
        except OSError:
            pass
    if remove_folder:
        try:
            folder.rmdir()
        except OSError:
            pass


def store_feature_upload(
    features_root: str | Path,
    feature_key: str,
    *,
    spec_stream: BinaryIO,
    events_stream: BinaryIO,
    max_spec_bytes: int,
    max_event_bytes: int = DEFAULT_MAX_EVENT_FILE_BYTES,
) -> Path:
    """Store multipart roles under canonical names, replacing prior inputs."""

    validate_feature_key(feature_key)
    if max_spec_bytes < 1 or max_event_bytes < 1:
        raise ValueError("Upload byte limits must be positive")

    root = _resolved_root(features_root)
    folder = root / feature_key
    created_folder = False
    try:
        folder.mkdir(mode=0o700)
        created_folder = True
    except FileExistsError:
        if not folder.is_dir() or folder.is_symlink():
            raise FeatureUploadStorageError(
                f"Feature path is not a writable folder: {feature_key}"
            )
    except OSError as exc:
        raise FeatureUploadStorageError(
            f"Could not create feature folder: {feature_key}"
        ) from exc

    temporary_spec = folder / f".{SPEC_FILENAME}.upload"
    temporary_events = folder / f".{EVENTS_FILENAME}.upload"
    try:
        _copy_bounded(
            spec_stream,
            temporary_spec,
            label=SPEC_FILENAME,
            max_bytes=max_spec_bytes,
        )
        _copy_bounded(
            events_stream,
            temporary_events,
            label=EVENTS_FILENAME,
            max_bytes=max_event_bytes,
        )
        temporary_spec.replace(folder / SPEC_FILENAME)
        temporary_events.replace(folder / EVENTS_FILENAME)
    except Exception:
        _clean_failed_upload(folder, remove_folder=created_folder)
        raise

    return folder


__all__ = [
    "DEFAULT_MAX_EVENT_FILE_BYTES",
    "EmptyUploadedFileError",
    "FeatureUploadError",
    "FeatureUploadStorageError",
    "UploadedFileTooLargeError",
    "store_feature_upload",
]
