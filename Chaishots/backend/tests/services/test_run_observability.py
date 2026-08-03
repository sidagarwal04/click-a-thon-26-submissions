from __future__ import annotations

from typing import Any

from app.services.run_observability import LangfuseRunObservability


class FakeModel:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        assert mode == "json"
        return self.payload


class FakeTraceClient:
    def list(self, **kwargs: object) -> FakeModel:
        assert kwargs == {"page": 1, "limit": 25, "order_by": "timestamp.desc"}
        return FakeModel(
            {
                "data": [
                    {
                        "id": "trace-1",
                        "name": "process_feature",
                        "timestamp": "2026-08-01T11:05:02Z",
                        "updatedAt": "2026-08-01T11:05:49Z",
                        "latency": 47.9,
                        "totalCost": 0.12,
                        "environment": "default",
                        "observations": ["span-1", "span-2"],
                        "output": '{"status":"completed","feature":"checkout"}',
                    }
                ],
                "meta": {"page": 1, "limit": 25, "total_items": 1, "total_pages": 1},
            }
        )

    def get(self, trace_id: str, **kwargs: object) -> FakeModel:
        assert trace_id == "trace-1"
        return FakeModel(
            {
                "id": "trace-1",
                "name": "process_feature",
                "timestamp": "2026-08-01T11:05:02Z",
                "latency": 2.0,
                "input": '{"feature_folder":"checkout"}',
                "output": {"status": "completed", "run_id": "run-1"},
                "htmlPath": "/project/example/traces/trace-1",
                "observations": [
                    {
                        "id": "root",
                        "traceId": "trace-1",
                        "parentObservationId": None,
                        "name": "process_feature",
                        "type": "SPAN",
                        "startTime": "2026-08-01T11:05:02Z",
                        "endTime": "2026-08-01T11:05:04Z",
                        "latency": 2.0,
                    },
                    {
                        "id": "child",
                        "traceId": "trace-1",
                        "parentObservationId": "root",
                        "name": "profile_events",
                        "type": "SPAN",
                        "startTime": "2026-08-01T11:05:02.250Z",
                        "endTime": "2026-08-01T11:05:02.500Z",
                        "latency": 0.25,
                        "output": '{"event_count":100}',
                    },
                ],
            }
        )


class FakeAPI:
    trace = FakeTraceClient()


class FakeClient:
    api = FakeAPI()


def test_list_runs_handles_compact_observation_ids_and_decodes_output() -> None:
    service = LangfuseRunObservability(FakeClient())

    response = service.list_runs(page=1, limit=25)

    assert response["meta"]["total_items"] == 1
    assert response["data"][0]["feature"] == "checkout"
    assert response["data"][0]["status"] == "completed"
    assert response["data"][0]["observation_count"] == 2


def test_get_run_normalizes_observations_timing_and_link() -> None:
    service = LangfuseRunObservability(
        FakeClient(), base_url="https://cloud.langfuse.com"
    )

    response = service.get_run("trace-1")

    assert response["input"] == {"feature_folder": "checkout"}
    assert response["pipeline_run_id"] == "run-1"
    assert response["html_path"] == (
        "https://cloud.langfuse.com/project/example/traces/trace-1"
    )
    assert response["observations"][1]["offset_ms"] == 250
    assert response["observations"][1]["output"] == {"event_count": 100}
