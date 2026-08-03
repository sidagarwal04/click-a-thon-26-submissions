from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.cli import run_cli
from app.schemas.features import (
    ContextDiff,
    EventProfile,
    InsightSummary,
    ProcessFeatureResult,
    RunReport,
    RunSummary,
    SchemaArtifact,
)


def make_process_result() -> ProcessFeatureResult:
    return ProcessFeatureResult(
        run_id="11111111-1111-4111-8111-111111111111",
        status="profiled",
        feature="01_express_checkout",
        table_created="express_checkout_events",
        rows_loaded=12,
        context_version=2,
        insights=[InsightSummary(title="Checkout converts", confidence="high")],
        langfuse_trace_id="trace-test-1",
        event_profile=EventProfile(
            event_count=12,
            event_names={"express_checkout_shown": 12},
            fields={},
        ),
    )


@dataclass(slots=True)
class FakePipeline:
    """One typed FeaturePipeline test double shared by all adapter tests."""

    result: ProcessFeatureResult = field(default_factory=make_process_result)
    run_summary: RunSummary = field(
        default_factory=lambda: RunSummary(
            run_id="11111111-1111-4111-8111-111111111111",
            status="profiled",
            feature="01_express_checkout",
            table_created="express_checkout_events",
            rows_loaded=12,
            context_version=2,
            insights=[InsightSummary(title="Checkout converts", confidence="high")],
            langfuse_trace_id="trace-test-1",
        )
    )
    schema: SchemaArtifact = field(
        default_factory=lambda: SchemaArtifact(
            run_id="11111111-1111-4111-8111-111111111111",
            table_name="express_checkout_events",
            ddl="CREATE TABLE express_checkout_events (event_id String)",
            partition_by=None,
            partition_by_reasoning="The table does not require partitions",
            schema={"event_id": "String"},
        )
    )
    context_diff: ContextDiff = field(
        default_factory=lambda: ContextDiff(
            run_id="11111111-1111-4111-8111-111111111111",
            context_version=2,
            relationships_added=[{"source_table": "express_checkout_events"}],
            metrics_added=[{"name": "checkout_conversion"}],
            conflicts=[],
        )
    )
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[tuple[str, str | None]] = field(default_factory=list, init=False)
    flush_calls: int = field(default=0, init=False)

    def _record(self, operation: str, value: str) -> None:
        self.calls.append((operation, value))
        error = self.errors.get(operation)
        if error is not None:
            raise error

    def process_feature(self, feature_folder: str) -> ProcessFeatureResult:
        self._record("process_feature", feature_folder)
        return self.result

    def get_run_summary(self, run_id: str) -> RunSummary:
        self._record("get_run_summary", run_id)
        return self.run_summary

    def get_schema(self, run_id: str) -> SchemaArtifact:
        self._record("get_schema", run_id)
        return self.schema

    def get_context_diff(self, run_id: str) -> ContextDiff:
        self._record("get_context_diff", run_id)
        return self.context_diff

    def get_insights(self, run_id: str) -> list[InsightSummary]:
        self._record("get_insights", run_id)
        return list(self.run_summary.insights)

    def get_run_report(self, run_id: str) -> RunReport:
        self._record("get_run_report", run_id)
        return RunReport(summary=self.run_summary, artifacts={})

    def flush_traces(self) -> None:
        self.calls.append(("flush_traces", None))
        self.flush_calls += 1
        error = self.errors.get("flush_traces")
        if error is not None:
            raise error


def test_cli_delegates_to_shared_pipeline_and_prints_structured_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakePipeline()

    exit_code = run_cli(
        ["--feature", "01_express_checkout"],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert ProcessFeatureResult.model_validate_json(captured.out) == service.result
    assert service.calls == [
        ("process_feature", "01_express_checkout"),
        ("flush_traces", None),
    ]
    assert service.flush_calls == 1


def test_cli_returns_failure_and_still_flushes_traces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakePipeline(errors={"process_feature": RuntimeError("test failure")})

    exit_code = run_cli(["--feature", "broken_feature"], service=service)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Pipeline failed: test failure\n"
    assert service.calls == [
        ("process_feature", "broken_feature"),
        ("flush_traces", None),
    ]
    assert service.flush_calls == 1


def test_cli_keeps_successful_result_when_trace_flush_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakePipeline(errors={"flush_traces": RuntimeError("export unavailable")})

    exit_code = run_cli(
        ["--feature", "01_express_checkout"],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert ProcessFeatureResult.model_validate_json(captured.out) == service.result
    assert captured.err == "Trace flush failed: export unavailable\n"
    assert service.calls == [
        ("process_feature", "01_express_checkout"),
        ("flush_traces", None),
    ]
    assert service.flush_calls == 1
