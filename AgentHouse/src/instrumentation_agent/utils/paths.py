"""Resolve feature ``spec.md`` paths (events.ndjson is optional / unused by the workflow)."""

from __future__ import annotations

from pathlib import Path

from instrumentation_agent.models.domain import FeaturePaths
from instrumentation_agent.settings import Settings, get_settings


def feature_paths(feature_id: str, *, settings: Settings | None = None) -> FeaturePaths:
    """``SPECS_ROOT/{feature_id}/spec.md``."""
    cfg = settings or get_settings()
    feature_dir = Path(cfg.specs_root).expanduser().resolve() / feature_id
    return FeaturePaths(
        feature_id=feature_id,
        feature_dir=feature_dir,
        spec_path=feature_dir / "spec.md",
    )


def resolve_feature_paths(
    *,
    feature_id: str | None = None,
    spec_path: str | Path | None = None,
    settings: Settings | None = None,
) -> FeaturePaths:
    """Resolve paths for a feature pack from ``feature_id`` and/or ``spec_path``.

    - If ``spec_path`` is set: use that file; ``feature_id`` defaults to parent folder name.
    - Else: ``SPECS_ROOT/{feature_id}/spec.md``.
    """
    if spec_path is not None:
        spec = Path(spec_path).expanduser().resolve()
        feature_dir = spec.parent
        fid = feature_id or feature_dir.name
        return FeaturePaths(
            feature_id=fid,
            feature_dir=feature_dir,
            spec_path=spec,
        )

    if not feature_id:
        raise ValueError("feature_id is required when spec_path is not provided")
    return feature_paths(feature_id, settings=settings)
