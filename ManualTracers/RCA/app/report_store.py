"""Persists investigation reports so rca-api can serve real ones instead of the
hardcoded rca-api/sample-reports.js — docs/RCA_UI_TEMPLATE.md, Step 2 (Option A: JSON
files on a shared volume). Skips Option B (a ClickHouse table) because that means
adding a ClickHouse client to rca-api, a Node process nothing else in this repo needs
one for — the shared filesystem is the whole integration, no database, no network hop.

One file per report, named by id, in Settings.rca_reports_dir.
"""

import json
from pathlib import Path

from app.settings import get_settings


def persist_report(report: dict, directory: Path | None = None) -> Path:
    target = directory or get_settings().rca_reports_dir
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{report['id']}.json"
    path.write_text(json.dumps(report, default=str, indent=2))
    return path
