"""The committed Connector contract and the application must not drift.

The frontend is built against `docs/05_APIs/connector-openapi.json`. If the
application changes and the document does not, the frontend is building against
a lie — and the failure surfaces as a confusing runtime error in a different
codebase, days later. This test turns that into a red build here.

Regenerate with:

    uv run python tools/scripts/export_connector_openapi.py
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zentra_api.main import create_app

COMMITTED = pathlib.Path(__file__).resolve().parents[3] / (
    "docs/05_APIs/connector-openapi.json"
)
PREFIX = "/v1/connector"


@pytest.fixture(scope="module")
def committed() -> dict:
    assert COMMITTED.exists(), f"Contract not found at {COMMITTED}"
    return json.loads(COMMITTED.read_text())


@pytest.fixture(scope="module")
def generated() -> dict:
    return create_app().openapi()


def test_committed_contract_matches_the_application(committed, generated) -> None:
    """Full equality over the connector surface, not a spot check.

    Compared as whole path objects so an added parameter, a changed status code,
    or an altered response schema all fail — not only an added or removed route.
    """
    live = {p: v for p, v in generated["paths"].items() if p.startswith(PREFIX)}

    assert committed["paths"] == live


def test_every_connector_route_is_in_the_contract(generated, committed) -> None:
    live = {p for p in generated["paths"] if p.startswith(PREFIX)}

    assert live == set(committed["paths"])


def test_no_response_schema_carries_a_credential(committed) -> None:
    """The write-only guarantee, asserted over the document a client reads.

    Checked against the serialised contract rather than the Python models
    because that is what a frontend consumes: if the word appears in a response
    schema here, something leaks regardless of what the models intended.
    """
    schemas = committed.get("components", {}).get("schemas", {})
    response_schemas = {
        name: schema
        for name, schema in schemas.items()
        if name.endswith("Response") or name.endswith("Summary")
    }
    assert response_schemas, "No response schemas found; the check would be vacuous"

    for name, schema in response_schemas.items():
        properties = set(schema.get("properties", {}))
        leaked = properties & {"password", "credentials", "username", "secret"}
        assert not leaked, f"{name} exposes {leaked}"


def test_the_credentials_request_schema_is_request_only(committed) -> None:
    """Credentials may be accepted; they may never be returned."""
    schemas = committed.get("components", {}).get("schemas", {})
    assert "SourceCredentialsRequest" in schemas
    assert "SourceCredentialsResponse" not in schemas


def test_starting_a_harvest_is_documented_as_accepted(committed) -> None:
    """202 rather than 200: discovery does not finish inside a request."""
    path = committed["paths"][f"{PREFIX}/sources/{{data_source_id}}/harvests"]

    assert "202" in path["post"]["responses"]


def test_the_join_graph_endpoint_exists(committed) -> None:
    """The only surface an agent may take joins from."""
    assert (
        f"{PREFIX}/catalog-versions/{{catalog_version_id}}/join-graph"
        in committed["paths"]
    )


def test_the_contract_declares_its_own_title(committed) -> None:
    assert committed["info"]["title"] == "ZentraOS Connector API"
