"""Read-only access to the Click-a-thon GitHub repo only (no other repos)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import quote

import httpx

ALLOWED_OWNER = "sidagarwal04"
ALLOWED_REPO = "click-a-thon-2026"
DEFAULT_REF = "main"
DEFAULT_GLOSSARY_PATH = "InMobi/metrics_glossary.md"

GLOSSARY_HTML = (
    f"https://github.com/{ALLOWED_OWNER}/{ALLOWED_REPO}/blob/{DEFAULT_REF}/"
    f"{DEFAULT_GLOSSARY_PATH}"
)
RAW_BASE = f"https://raw.githubusercontent.com/{ALLOWED_OWNER}/{ALLOWED_REPO}"


def _validate_path(path: str) -> str:
    p = (path or "").strip().lstrip("/")
    if not p:
        raise ValueError("path is required")
    if p.startswith(".git") or ".." in p.split("/") or p.startswith("\\"):
        raise ValueError(f"path not allowed: {path}")
    # Only this repo's tree — reject absolute URLs / other owners
    if "://" in p or p.lower().startswith("github.com"):
        raise ValueError("pass a repo-relative path only, e.g. InMobi/metrics_glossary.md")
    return p


@lru_cache(maxsize=32)
def _fetch_raw(path: str, ref: str) -> str:
    url = f"{RAW_BASE}/{quote(ref, safe='')}/{quote(path, safe='/')}"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        if r.status_code == 404:
            raise FileNotFoundError(
                f"not found in {ALLOWED_OWNER}/{ALLOWED_REPO}@{ref}: {path}"
            )
        r.raise_for_status()
        return r.text


def get_clickathon_repo_file(
    path: str = DEFAULT_GLOSSARY_PATH,
    *,
    ref: str = DEFAULT_REF,
    refresh: bool = False,
) -> dict[str, Any]:
    """Fetch a file from sidagarwal04/click-a-thon-2026 only."""
    safe_path = _validate_path(path)
    safe_ref = (ref or DEFAULT_REF).strip() or DEFAULT_REF
    if refresh:
        _fetch_raw.cache_clear()
    content = _fetch_raw(safe_path, safe_ref)
    return {
        "owner": ALLOWED_OWNER,
        "repo": ALLOWED_REPO,
        "ref": safe_ref,
        "path": safe_path,
        "html_url": (
            f"https://github.com/{ALLOWED_OWNER}/{ALLOWED_REPO}/blob/"
            f"{safe_ref}/{safe_path}"
        ),
        "raw_url": f"{RAW_BASE}/{safe_ref}/{safe_path}",
        "content": content,
        "note": (
            "This tool is locked to one repository "
            f"({ALLOWED_OWNER}/{ALLOWED_REPO}). Other GitHub repos are not accessible."
        ),
    }


def get_metrics_glossary(*, refresh: bool = False) -> dict[str, Any]:
    """Official InMobi metrics glossary from the locked Click-a-thon repo."""
    file = get_clickathon_repo_file(DEFAULT_GLOSSARY_PATH, refresh=refresh)
    return {
        "source": {
            "owner": ALLOWED_OWNER,
            "repo": ALLOWED_REPO,
            "path": DEFAULT_GLOSSARY_PATH,
            "ref": DEFAULT_REF,
            "html_url": GLOSSARY_HTML,
        },
        "raw_url": file["raw_url"],
        "markdown": file["content"],
        "rules_summary": [
            "Compute ratio metrics as sum/sum over the group — never avg of ratios.",
            "Revenue ≈ Requests × Fill rate × eCPM / 1000 (when ~1 impression per fill).",
            "CTR is context, not a direct revenue factor in this CPM model.",
            "North America region code is NAM (not NA).",
            "advertiser_id empty on unfilled requests — vertical/campaign only on fills.",
            "Use like-for-like baselines (same weekday); weekends are lower volume.",
        ],
        "note": file["note"],
    }
