"""Export the complete API and versioned public chat contracts."""

from __future__ import annotations

import json
from pathlib import Path

from zentra_api.main import create_app
from zentra_domain_investigation import ThreadEvent, VisualizationBriefV1

API_DESTINATION = Path("docs/05_APIs/zentraos-openapi.json")
SCHEMA_DIRECTORY = Path("docs/05_APIs/schemas")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    _write(API_DESTINATION, create_app().openapi())
    _write(
        SCHEMA_DIRECTORY / "visualization-brief-v1.schema.json",
        VisualizationBriefV1.model_json_schema(),
    )
    _write(
        SCHEMA_DIRECTORY / "work-feed-event.schema.json",
        ThreadEvent.model_json_schema(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
