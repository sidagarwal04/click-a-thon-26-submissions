from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import JsonValue

from app.core.config import Settings
from app.repositories.clickhouse import ClickHouseRepository
from app.repositories.run_store import RunStore
from app.schemas.features import (
    ContextDiff,
    EventProfile,
    InsightSummary,
    ProcessFeatureResult,
    RunSummary,
    SchemaArtifact,
)
from app.services.feature_pipeline import FeaturePipelineService
from app.tools.feature_source import InvalidFeatureKeyError
from app.tracing import ObservationType, SpanLevel, Tracer, TraceSpan


class FakeClickHouse(ClickHouseRepository):
    """Typed repository double for the two pipeline preflight operations."""

    def __init__(self, *, tables: Sequence[str] = (), ping_result: bool = True) -> None:
        self.tables = list(tables)
        self.ping_result = ping_result
        self.calls: list[str] = []

    def ping(self) -> bool:
        self.calls.append("SELECT 1")
        return self.ping_result

    def list_tables(self, database: str | None = None) -> list[str]:
        self.calls.append("list_tables")
        return list(self.tables)


@dataclass(frozen=True, slots=True)
class SavedProfiledRun:
    result: ProcessFeatureResult
    event_profile: EventProfile
    spec_sha256: str
    available_tables: list[str]


class FakeRunStore(RunStore):
    def __init__(
        self,
        *,
        summary: RunSummary | None = None,
        artifacts: Mapping[tuple[str, str], JsonValue] | None = None,
    ) -> None:
        self.summary = summary
        self.artifacts = dict(artifacts or {})
        self.saved: list[SavedProfiledRun] = []
        self.summary_calls: list[str] = []
        self.artifact_calls: list[tuple[str, str]] = []

    def save_profiled_run(
        self,
        result: ProcessFeatureResult,
        *,
        event_profile: EventProfile,
        spec_sha256: str,
        available_tables: Sequence[str],
    ) -> None:
        self.saved.append(
            SavedProfiledRun(
                result=result,
                event_profile=event_profile,
                spec_sha256=spec_sha256,
                available_tables=list(available_tables),
            )
        )

    def get_run_summary(self, run_id: str) -> RunSummary:
        self.summary_calls.append(run_id)
        if self.summary is None:
            raise AssertionError("No fake run summary configured")
        return self.summary

    def get_artifact(self, run_id: str, artifact_type: str) -> JsonValue:
        self.artifact_calls.append((run_id, artifact_type))
        return self.artifacts[(run_id, artifact_type)]


class FakeSpan:
    def __init__(self, trace_id: str) -> None:
        self._trace_id = trace_id
        self.updates: list[dict[str, object]] = []

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def update(
        self,
        *,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
        level: SpanLevel | None = None,
        status: str | None = None,
    ) -> None:
        self.updates.append(
            {
                "output": output,
                "metadata": metadata,
                "level": level,
                "status": status,
            }
        )


class FakeTracer(Tracer):
    def __init__(self, trace_id: str = "trace-test-123") -> None:
        self.trace_id = trace_id
        self.starts: list[tuple[str, object | None, ObservationType]] = []
        self.spans: list[FakeSpan] = []
        self.flush_count = 0

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input: object | None = None,
        as_type: ObservationType = "span",
    ) -> Iterator[TraceSpan]:
        span = FakeSpan(self.trace_id)
        self.starts.append((name, input, as_type))
        self.spans.append(span)
        yield span

    def flush(self) -> None:
        self.flush_count += 1


def _make_settings(feature_root: Path) -> Settings:
    return Settings.model_validate(
        {
            "PROJECT_NAME": "pipeline-test",
            "FEATURE_ROOT": feature_root,
            "FEATURE_MAX_SPEC_BYTES": 4096,
            "FEATURE_MAX_EVENT_LINE_BYTES": 4096,
            "FEATURE_CARDINALITY_SAMPLE_SIZE": 16,
        }
    )


def _write_feature(feature_root: Path) -> tuple[str, str]:
    feature = "01_checkout"
    spec = "# Express checkout\nMeasure completion by platform."
    folder = feature_root / feature
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(spec, encoding="utf-8")
    (folder / "events.ndjson").write_text(
        "\n".join(
            [
                '{"event_name":"shown","user_id":"u1","platform":"ios"}',
                '{"event":"selected","user_id":"u1","platform":"ios"}',
                '{"type":"shown","user_id":"u2","platform":"android"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return feature, spec


def _make_service(
    feature_root: Path,
    *,
    clickhouse: FakeClickHouse,
    run_store: FakeRunStore,
    tracer: FakeTracer,
) -> FeaturePipelineService:
    return FeaturePipelineService(
        config=_make_settings(feature_root),
        clickhouse=clickhouse,
        run_store=run_store,
        tracer=tracer,
    )


def test_process_feature_profiles_streamed_inputs_preflights_and_persists(
    tmp_path: Path,
) -> None:
    feature, spec = _write_feature(tmp_path)
    clickhouse = FakeClickHouse(tables=["purchase_completed", "search_typed"])
    run_store = FakeRunStore()
    tracer = FakeTracer()
    service = _make_service(
        tmp_path,
        clickhouse=clickhouse,
        run_store=run_store,
        tracer=tracer,
    )

    result = service.process_feature(feature)

    UUID(result.run_id)
    assert result.status == "profiled"
    assert result.feature == feature
    assert result.rows_loaded == 0
    assert result.event_profile is None
    assert result.langfuse_trace_id == "trace-test-123"
    assert "spec" not in result.model_dump(exclude_none=True)
    assert clickhouse.calls == ["SELECT 1", "list_tables"]

    assert len(run_store.saved) == 1
    saved = run_store.saved[0]
    assert saved.result is result
    assert saved.spec_sha256 == hashlib.sha256(spec.encode("utf-8")).hexdigest()
    assert saved.available_tables == ["purchase_completed", "search_typed"]
    assert saved.event_profile.event_count == 3
    assert saved.event_profile.event_names == {"shown": 2, "selected": 1}
    assert saved.event_profile.fields["user_id"].approx_cardinality == 2
    assert saved.event_profile.fields["platform"].examples == ["ios", "android"]

    assert [name for name, _input, _type in tracer.starts] == [
        "process_feature",
        "read_feature_files",
        "profile_events",
        "clickhouse_preflight",
        "persist_profiled_run",
    ]


def test_process_feature_rejects_traversal_before_datastore_access(
    tmp_path: Path,
) -> None:
    clickhouse = FakeClickHouse()
    run_store = FakeRunStore()
    tracer = FakeTracer()
    service = _make_service(
        tmp_path,
        clickhouse=clickhouse,
        run_store=run_store,
        tracer=tracer,
    )

    with pytest.raises(InvalidFeatureKeyError):
        service.process_feature("../outside")

    assert clickhouse.calls == []
    assert run_store.saved == []


def test_read_methods_and_trace_flush_delegate_to_shared_dependencies(
    tmp_path: Path,
) -> None:
    run_id = "bd89117a-78ee-46da-b017-09bddf9d82c0"
    insight = InsightSummary(title="OTP completion is weaker", confidence="high")
    summary = RunSummary(
        run_id=run_id,
        status="completed",
        feature="01_checkout",
        table_created="checkout_events",
        rows_loaded=42,
        context_version=2,
        insights=[insight],
        langfuse_trace_id="trace-1",
    )
    schema_payload: JsonValue = {
        "run_id": run_id,
        "table_name": "checkout_events",
        "ddl": "CREATE TABLE checkout_events (event_name String)",
        "schema": {"event_name": "String"},
    }
    context_payload: JsonValue = {
        "run_id": run_id,
        "context_version": 2,
        "relationships_added": [],
        "metrics_added": [{"name": "checkout_completion"}],
        "conflicts": [],
    }
    run_store = FakeRunStore(
        summary=summary,
        artifacts={
            (run_id, "schema"): schema_payload,
            (run_id, "context_diff"): context_payload,
        },
    )
    tracer = FakeTracer()
    service = _make_service(
        tmp_path,
        clickhouse=FakeClickHouse(),
        run_store=run_store,
        tracer=tracer,
    )

    assert service.get_run_summary(run_id) is summary
    assert service.get_schema(run_id) == SchemaArtifact.model_validate(schema_payload)
    assert service.get_context_diff(run_id) == ContextDiff.model_validate(
        context_payload
    )
    assert service.get_insights(run_id) == [insight]
    service.flush_traces()

    assert run_store.summary_calls == [run_id, run_id]
    assert run_store.artifact_calls == [
        (run_id, "schema"),
        (run_id, "context_diff"),
    ]
    assert tracer.flush_count == 1
