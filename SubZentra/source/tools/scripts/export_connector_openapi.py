"""Export the Connector OpenAPI document from the running application.

Contract-first would normally mean hand-writing the document and asserting the
application matches it. That ordering exists to unblock a frontend before the
backend is written; here the routes landed first, so the document is generated
from them and then *frozen* by a test. The guarantee a consumer needs — that the
committed document and the application cannot drift apart — is the same either
way, and generating removes a class of transcription error.

Run: uv run python tools/scripts/export_connector_openapi.py
"""

from __future__ import annotations

import json
import pathlib
import sys

from zentra_api.main import create_app

DESTINATION = pathlib.Path("docs/05_APIs/connector-openapi.json")
PREFIX = "/v1/connector"


def connector_spec() -> dict:
    """The connector slice of the application's specification.

    Sliced rather than exported whole so that a change to the Investigation API
    cannot fail the connector contract test, and so a frontend agent reading
    this file sees only the surface it is building against. Schemas are kept
    entire because slicing them by reachability would silently drop a shared
    model the moment one stopped being referenced.
    """
    spec = create_app().openapi()
    return {
        "openapi": spec["openapi"],
        "info": {
            "title": "ZentraOS Connector API",
            "version": spec["info"]["version"],
            "description": (
                "Data Sources, metadata harvest, and governed field Relations. "
                "Credentials are write-only: no response schema carries one."
            ),
        },
        "paths": {p: v for p, v in spec["paths"].items() if p.startswith(PREFIX)},
        "components": spec.get("components", {}),
    }


def main() -> int:
    document = json.dumps(connector_spec(), indent=2, sort_keys=True) + "\n"
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(document)
    print(f"wrote {DESTINATION} ({len(document)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
