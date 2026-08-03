from __future__ import annotations

import json
from pathlib import Path

from zentra_domain_investigation import ThreadEvent, VisualizationBriefV1

from zentra_api.main import create_app

ROOT = Path(__file__).parents[3]


def test_complete_openapi_snapshot_matches_application() -> None:
    expected = json.loads((ROOT / "docs/05_APIs/zentraos-openapi.json").read_text())
    assert expected == create_app().openapi()


def test_versioned_public_schemas_match_domain() -> None:
    brief = json.loads(
        (ROOT / "docs/05_APIs/schemas/visualization-brief-v1.schema.json").read_text()
    )
    feed = json.loads(
        (ROOT / "docs/05_APIs/schemas/work-feed-event.schema.json").read_text()
    )
    assert brief == VisualizationBriefV1.model_json_schema()
    assert feed == ThreadEvent.model_json_schema()


def test_public_feed_contract_cannot_represent_sensitive_surfaces() -> None:
    feed = (
        (ROOT / "docs/05_APIs/schemas/work-feed-event.schema.json")
        .read_text()
        .casefold()
    )
    for prohibited in (
        '"prompt"',
        '"reasoning"',
        '"sql"',
        '"raw_rows"',
        '"credentials"',
        '"provider_body"',
    ):
        assert prohibited not in feed


def test_backend_journey_contract_and_fixtures_are_complete() -> None:
    paths = create_app().openapi()["paths"]
    for path in (
        "/v1/groups",
        "/v1/groups/{group_id}/projects",
        "/v1/projects/{project_id}/threads",
        "/v1/threads/{thread_id}/messages",
        "/v1/threads/{thread_id}/events",
        "/v1/investigations/{investigation_id}/approvals/{approval_id}/decision",
        "/v1/investigations/{investigation_id}/visualization",
        "/v1/visualizations/{visualization_id}/actions/{action_id}/execute",
    ):
        assert path in paths
    states = json.loads(
        (ROOT / "docs/05_APIs/fixtures/chat-thread-states.json").read_text()
    )["states"]
    assert {
        "clarification",
        "agents_queued",
        "agents_running",
        "approval",
        "finding",
        "visualization_ready",
        "visualization_failed",
        "visualization_retried",
        "action_rejected",
        "tombstone",
    } == set(states)
