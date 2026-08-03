from __future__ import annotations

import json
from functools import lru_cache
from importlib import import_module
from typing import Any, Protocol, cast
from urllib.parse import urljoin

from app.core.config import Settings, settings


class RunObservabilityError(RuntimeError):
    """Raised when the run explorer cannot read Langfuse."""


class RunObservabilityNotConfiguredError(RunObservabilityError):
    """Raised when the server has no Langfuse credentials."""


class RunObservabilityNotFoundError(RunObservabilityError):
    """Raised when Langfuse has no trace with the requested id."""


class RunObservability(Protocol):
    def list_runs(self, *, page: int, limit: int) -> dict[str, Any]: ...

    def get_run(self, trace_id: str) -> dict[str, Any]: ...


class _Model(Protocol):
    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _TraceClient(Protocol):
    def list(self, **kwargs: object) -> _Model: ...

    def get(self, trace_id: str, **kwargs: object) -> _Model: ...


class _API(Protocol):
    trace: _TraceClient


class _LangfuseClient(Protocol):
    api: _API


class LangfuseRunObservability:
    """Read-only, frontend-safe view over the Langfuse trace API."""

    def __init__(self, client: _LangfuseClient, *, base_url: str | None = None) -> None:
        self._client = client
        self._base_url = base_url

    def list_runs(self, *, page: int, limit: int) -> dict[str, Any]:
        try:
            response = self._client.api.trace.list(
                page=page,
                limit=limit,
                order_by="timestamp.desc",
            )
        except Exception as exc:
            raise RunObservabilityError("Could not load runs from Langfuse") from exc

        payload = response.model_dump(mode="json")
        runs = [_run_summary(item) for item in payload.get("data", [])]
        meta = payload.get("meta") or {}
        return {
            "data": runs,
            "meta": {
                "page": int(meta.get("page", page)),
                "limit": int(meta.get("limit", limit)),
                "total_items": int(meta.get("total_items", len(runs))),
                "total_pages": int(meta.get("total_pages", 1)),
            },
        }

    def get_run(self, trace_id: str) -> dict[str, Any]:
        try:
            response = self._client.api.trace.get(trace_id)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 404 or "status_code: 404" in str(exc):
                raise RunObservabilityNotFoundError(
                    f"Langfuse run not found: {trace_id}"
                ) from exc
            raise RunObservabilityError("Could not load the run from Langfuse") from exc

        trace = response.model_dump(mode="json")
        observations = [_observation(item) for item in trace.get("observations", [])]
        observations.sort(key=lambda item: _timestamp_sort(item.get("start_time")))
        started_at = trace.get("timestamp")
        for observation in observations:
            observation["offset_ms"] = _offset_ms(
                started_at, observation.get("start_time")
            )

        summary = _run_summary(trace)
        summary.update(
            {
                "input": _decode_json(trace.get("input")),
                "output": _decode_json(trace.get("output")),
                "metadata": trace.get("metadata") or {},
                "scores": trace.get("scores") or [],
                "observations": observations,
                "html_path": _absolute_url(self._base_url, trace.get("htmlPath")),
            }
        )
        return summary


def _run_summary(trace: dict[str, Any]) -> dict[str, Any]:
    observations = trace.get("observations") or []
    error_count = sum(
        1
        for item in observations
        if isinstance(item, dict)
        and (
            str(item.get("level", "")).upper() == "ERROR"
            or bool(item.get("statusMessage"))
        )
    )
    output = _decode_json(trace.get("output"))
    status = "error" if error_count else "completed"
    if isinstance(output, dict) and isinstance(output.get("status"), str):
        status = output["status"]
    return {
        "id": trace.get("id"),
        "name": trace.get("name") or "Untitled run",
        "timestamp": trace.get("timestamp"),
        "updated_at": trace.get("updatedAt"),
        "latency": trace.get("latency"),
        "total_cost": trace.get("totalCost"),
        "environment": trace.get("environment"),
        "release": trace.get("release"),
        "version": trace.get("version"),
        "user_id": trace.get("userId"),
        "session_id": trace.get("sessionId"),
        "tags": trace.get("tags") or [],
        "status": status,
        "error_count": error_count,
        "observation_count": len(observations),
        "feature": output.get("feature") if isinstance(output, dict) else None,
        "pipeline_run_id": output.get("run_id") if isinstance(output, dict) else None,
    }


def _observation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "trace_id": item.get("traceId"),
        "parent_observation_id": item.get("parentObservationId"),
        "name": item.get("name") or "Untitled step",
        "type": item.get("type") or "SPAN",
        "start_time": item.get("startTime"),
        "end_time": item.get("endTime"),
        "completion_start_time": item.get("completionStartTime"),
        "latency": item.get("latency"),
        "level": item.get("level") or "DEFAULT",
        "status_message": item.get("statusMessage") or None,
        "input": _decode_json(item.get("input")),
        "output": _decode_json(item.get("output")),
        "metadata": item.get("metadata") or {},
        "model": item.get("model"),
        "model_parameters": item.get("modelParameters") or {},
        "usage": item.get("usage") or item.get("usageDetails") or {},
        "cost": item.get("calculatedTotalCost") or item.get("totalPrice"),
        "cost_details": item.get("costDetails") or {},
        "time_to_first_token": item.get("timeToFirstToken"),
        "prompt_name": item.get("promptName"),
        "prompt_version": item.get("promptVersion"),
    }


def _decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _offset_ms(start: Any, current: Any) -> int:
    if not isinstance(start, str) or not isinstance(current, str):
        return 0
    from datetime import datetime

    try:
        return max(
            0,
            round(
                (datetime.fromisoformat(current.replace("Z", "+00:00"))
                - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
                * 1000
            ),
        )
    except ValueError:
        return 0


def _timestamp_sort(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _absolute_url(base_url: str | None, path: Any) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    if not base_url:
        return path
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def build_run_observability(config: Settings) -> RunObservability:
    if not config.LANGFUSE_PUBLIC_KEY or config.LANGFUSE_SECRET_KEY is None:
        raise RunObservabilityNotConfiguredError(
            "Langfuse credentials are not configured on the backend"
        )
    module = import_module("langfuse")
    base_url = (
        str(config.LANGFUSE_BASE_URL).rstrip("/")
        if config.LANGFUSE_BASE_URL is not None
        else None
    )
    client = module.Langfuse(
        public_key=config.LANGFUSE_PUBLIC_KEY,
        secret_key=config.LANGFUSE_SECRET_KEY.get_secret_value(),
        base_url=base_url,
    )
    return LangfuseRunObservability(
        cast(_LangfuseClient, client), base_url=base_url
    )


@lru_cache
def get_run_observability() -> RunObservability:
    return build_run_observability(settings)
