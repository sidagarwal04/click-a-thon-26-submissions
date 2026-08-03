from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.pipeline import FeatureUploadStore, get_feature_upload_store
from app.main import app
from app.repositories.clickhouse import ClickHouseNotConfiguredError
from app.services.feature_pipeline import (
    FeaturePipeline,
    get_feature_pipeline_service,
)
from app.tools.feature_source import (
    FeatureNotFoundError,
    InvalidFeatureKeyError,
)
from tests.test_cli import FakePipeline

API_PREFIX = "/api/v1"


@contextmanager
def client_for(
    service: FakePipeline,
    upload_store: FeatureUploadStore | None = None,
) -> Generator[TestClient]:
    def override_service() -> FeaturePipeline:
        return service

    app.dependency_overrides[get_feature_pipeline_service] = override_service
    if upload_store is not None:
        app.dependency_overrides[get_feature_upload_store] = lambda: upload_store
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_feature_pipeline_service, None)
        app.dependency_overrides.pop(get_feature_upload_store, None)


def test_post_upload_feature_only_stores_files(
    tmp_path: Path,
) -> None:
    service = FakePipeline()
    upload_store = FeatureUploadStore(tmp_path)

    with client_for(service, upload_store) as client:
        response = client.post(
            f"{API_PREFIX}/features/upload",
            data={"feature_folder": "01_express_checkout"},
            files={
                "spec": ("checkout-brief.txt", b"# Express checkout", "text/plain"),
                "events": (
                    "checkout-export.jsonl",
                    b'{"event_name":"checkout_started"}\n',
                    "application/x-ndjson",
                ),
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "feature_folder": "01_express_checkout",
        "status": "uploaded",
        "files": ["spec.md", "events.ndjson"],
    }
    folder = tmp_path / "01_express_checkout"
    assert (folder / "spec.md").read_text(encoding="utf-8") == "# Express checkout"
    assert (folder / "events.ndjson").read_bytes() == (
        b'{"event_name":"checkout_started"}\n'
    )
    assert service.calls == []


def test_post_upload_feature_replaces_existing_folder_inputs(
    tmp_path: Path,
) -> None:
    service = FakePipeline()
    existing = tmp_path / "existing_feature"
    existing.mkdir()
    (existing / "spec.md").write_text("keep me", encoding="utf-8")

    with client_for(service, FeatureUploadStore(tmp_path)) as client:
        response = client.post(
            f"{API_PREFIX}/features/upload",
            data={"feature_folder": "existing_feature"},
            files={
                "spec": ("spec.md", b"replacement", "text/markdown"),
                "events": ("events.ndjson", b"{}\n", "application/x-ndjson"),
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "uploaded"
    assert (existing / "spec.md").read_text(encoding="utf-8") == "replacement"
    assert (existing / "events.ndjson").read_bytes() == b"{}\n"
    assert service.calls == []


def test_post_process_feature_delegates_to_shared_pipeline() -> None:
    service = FakePipeline()

    with client_for(service) as client:
        response = client.post(
            f"{API_PREFIX}/features/process",
            json={"feature_folder": "01_express_checkout"},
        )

    assert response.status_code == 200
    assert response.json() == service.result.model_dump(mode="json", by_alias=True)
    assert service.calls == [("process_feature", "01_express_checkout")]


def test_get_endpoints_delegate_to_shared_pipeline() -> None:
    service = FakePipeline()
    run_id = service.result.run_id

    with client_for(service) as client:
        summary_response = client.get(f"{API_PREFIX}/runs/{run_id}")
        schema_response = client.get(f"{API_PREFIX}/runs/{run_id}/schema")
        context_response = client.get(f"{API_PREFIX}/runs/{run_id}/context-diff")
        insights_response = client.get(f"{API_PREFIX}/runs/{run_id}/insights")
        report_response = client.get(f"{API_PREFIX}/runs/{run_id}/report")

    assert summary_response.status_code == 200
    assert summary_response.json() == service.run_summary.model_dump(mode="json")
    assert schema_response.status_code == 200
    assert schema_response.json() == service.schema.model_dump(
        mode="json", by_alias=True
    )
    assert context_response.status_code == 200
    assert context_response.json() == service.context_diff.model_dump(mode="json")
    assert insights_response.status_code == 200
    assert insights_response.json() == [
        insight.model_dump(mode="json") for insight in service.run_summary.insights
    ]
    assert report_response.status_code == 200
    assert report_response.json() == {
        "summary": service.run_summary.model_dump(mode="json"),
        "artifacts": {},
    }
    assert service.calls == [
        ("get_run_summary", run_id),
        ("get_schema", run_id),
        ("get_context_diff", run_id),
        ("get_insights", run_id),
        ("get_run_report", run_id),
    ]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (InvalidFeatureKeyError("invalid feature key"), 422),
        (FeatureNotFoundError("feature not found"), 404),
        (ClickHouseNotConfiguredError("ClickHouse is not configured"), 503),
    ],
)
def test_post_process_feature_maps_domain_errors(
    error: Exception,
    expected_status: int,
) -> None:
    service = FakePipeline(errors={"process_feature": error})

    with client_for(service) as client:
        response = client.post(
            f"{API_PREFIX}/features/process",
            json={"feature_folder": "requested_feature"},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}
    assert service.calls == [("process_feature", "requested_feature")]
