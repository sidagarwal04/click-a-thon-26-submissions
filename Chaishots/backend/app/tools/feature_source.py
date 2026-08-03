import re
from pathlib import Path

from app.schemas.features import FeatureFiles

SPEC_FILENAME = "spec.md"
EVENTS_FILENAME = "events.ndjson"
DEFAULT_MAX_SPEC_BYTES = 256 * 1024
FEATURE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class FeatureSourceError(Exception):
    """Base exception for safe feature-folder access."""


class InvalidFeatureKeyError(FeatureSourceError):
    """Raised when a feature key is not one conservative path segment."""


class FeatureRootError(FeatureSourceError):
    """Raised when the configured feature root cannot be used."""


class FeatureNotFoundError(FeatureSourceError):
    """Raised when a requested feature folder does not exist."""


class FeatureFileError(FeatureSourceError):
    """Raised when a required feature file is missing or unreadable."""


class FeatureFileTooLargeError(FeatureFileError):
    """Raised when a feature file exceeds its configured byte limit."""


class FeatureSourceSecurityError(FeatureSourceError):
    """Raised when a resolved feature path escapes the configured root."""


def validate_feature_key(feature_key: str) -> str:
    """Validate and return a safe, single-segment feature key."""

    if FEATURE_KEY_PATTERN.fullmatch(feature_key) is None:
        raise InvalidFeatureKeyError(
            "Feature key must be one path segment containing only letters, "
            "numbers, underscores, or hyphens (maximum 128 characters)."
        )
    return feature_key


def _resolve_root(features_root: str | Path) -> Path:
    root = Path(features_root)
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise FeatureRootError(f"Feature root does not exist: {root}") from exc

    if not resolved_root.is_dir():
        raise FeatureRootError(f"Feature root is not a directory: {root}")
    return resolved_root


def _ensure_contained(path: Path, root: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FeatureFileError(f"Required {label} does not exist: {path.name}") from exc
    except OSError as exc:
        raise FeatureFileError(
            f"Could not resolve required {label}: {path.name}"
        ) from exc

    if not resolved.is_relative_to(root):
        raise FeatureSourceSecurityError(
            f"Resolved {label} is outside the configured feature root."
        )
    return resolved


def resolve_feature_folder(features_root: str | Path, feature_key: str) -> Path:
    """Resolve a validated feature folder and guarantee root containment."""

    validate_feature_key(feature_key)
    root = _resolve_root(features_root)
    candidate = root / feature_key
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FeatureNotFoundError(f"Feature folder not found: {feature_key}") from exc
    except OSError as exc:
        raise FeatureNotFoundError(
            f"Could not resolve feature folder: {feature_key}"
        ) from exc

    if not resolved.is_relative_to(root):
        raise FeatureSourceSecurityError(
            "Resolved feature folder is outside the configured feature root."
        )
    if not resolved.is_dir():
        raise FeatureNotFoundError(f"Feature path is not a folder: {feature_key}")
    return resolved


def read_feature_files(
    features_root: str | Path,
    feature_key: str,
    *,
    max_spec_bytes: int = DEFAULT_MAX_SPEC_BYTES,
) -> FeatureFiles:
    """Read a bounded spec and return its validated NDJSON path."""

    if max_spec_bytes < 1:
        raise ValueError("max_spec_bytes must be at least 1")

    root = _resolve_root(features_root)
    folder = resolve_feature_folder(root, feature_key)
    spec_path = _ensure_contained(folder / SPEC_FILENAME, root, label=SPEC_FILENAME)
    events_path = _ensure_contained(
        folder / EVENTS_FILENAME, root, label=EVENTS_FILENAME
    )

    if not spec_path.is_file():
        raise FeatureFileError(f"Required {SPEC_FILENAME} is not a regular file.")
    if not events_path.is_file():
        raise FeatureFileError(f"Required {EVENTS_FILENAME} is not a regular file.")

    try:
        with spec_path.open("rb") as spec_file:
            spec_bytes = spec_file.read(max_spec_bytes + 1)
    except OSError as exc:
        raise FeatureFileError(f"Could not read required {SPEC_FILENAME}.") from exc

    if len(spec_bytes) > max_spec_bytes:
        raise FeatureFileTooLargeError(
            f"{SPEC_FILENAME} exceeds the {max_spec_bytes}-byte limit."
        )

    try:
        spec = spec_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FeatureFileError(f"{SPEC_FILENAME} must be valid UTF-8.") from exc

    return FeatureFiles(feature=feature_key, spec=spec, events_path=events_path)
