from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Protocol
from uuid import uuid4

from app.agents.fireworks import FireworksAgentClient
from app.core.config import Settings, settings
from app.repositories.clickhouse import (
    ClickHouseNotConfiguredError,
    ClickHouseRepository,
)
from app.repositories.run_store import (
    ArtifactNotFoundError,
    ClickHouseRunStore,
    RunStore,
    RunStoreError,
)
from app.schemas.features import (
    ContextDiff,
    ContextDocument,
    InsightSummary,
    ProcessFeatureResult,
    RunReport,
    RunSummary,
    SchemaArtifact,
)
from app.services.full_feature_workflow import FullFeatureWorkflow
from app.tools.event_profiler import profile_events
from app.tools.feature_source import read_feature_files
from app.tracing import Tracer, create_tracer


class FeaturePipelineError(RuntimeError):
    """Base error for deterministic pipeline orchestration."""


class ClickHousePreflightError(FeaturePipelineError):
    """Raised when the configured primary datastore fails its preflight."""


class FeaturePipeline(Protocol):
    """Shared use-case contract consumed by REST, MCP, CLI, and dashboards."""

    def process_feature(self, feature_folder: str) -> ProcessFeatureResult: ...

    def get_run_summary(self, run_id: str) -> RunSummary: ...

    def get_schema(self, run_id: str) -> SchemaArtifact: ...

    def get_context_diff(self, run_id: str) -> ContextDiff: ...

    def get_current_context(self) -> ContextDocument: ...

    def get_context_version(self, version: int) -> ContextDocument: ...

    def get_insights(self, run_id: str) -> list[InsightSummary]: ...

    def get_run_report(self, run_id: str) -> RunReport: ...

    def flush_traces(self) -> None: ...


class FeaturePipelineService:
    """The single transport-independent entry point for feature processing.

    This first vertical slice deliberately stops after deterministic input
    profiling and ClickHouse persistence. Later instrumentation, context, and
    analytics agents extend this method in place; none of the transport adapters
    need to change.
    """

    def __init__(
        self,
        *,
        config: Settings,
        clickhouse: ClickHouseRepository,
        run_store: RunStore,
        tracer: Tracer,
        full_workflow: FullFeatureWorkflow | None = None,
    ) -> None:
        self._config = config
        self._clickhouse = clickhouse
        self._run_store = run_store
        self._tracer = tracer
        self._full_workflow = full_workflow

    def process_feature(self, feature_folder: str) -> ProcessFeatureResult:
        run_id = str(uuid4())
        with self._tracer.span(
            "process_feature",
            input={"run_id": run_id, "feature_folder": feature_folder},
        ) as root_span:
            with self._tracer.span(
                "read_feature_files",
                input={"feature_folder": feature_folder},
            ) as read_span:
                files = read_feature_files(
                    self._config.FEATURE_ROOT,
                    feature_folder,
                    max_spec_bytes=self._config.FEATURE_MAX_SPEC_BYTES,
                )
                read_span.update(
                    output={
                        "feature": files.feature,
                        "spec_bytes": len(files.spec.encode("utf-8")),
                    }
                )

            with self._tracer.span("profile_events") as profile_span:
                event_profile = profile_events(
                    files.events_path,
                    max_line_bytes=self._config.FEATURE_MAX_EVENT_LINE_BYTES,
                    cardinality_sample_size=(
                        self._config.FEATURE_CARDINALITY_SAMPLE_SIZE
                    ),
                )
                profile_span.update(
                    output={
                        "event_count": event_profile.event_count,
                        "event_name_count": len(event_profile.event_names),
                        "field_count": len(event_profile.fields),
                    }
                )

            with self._tracer.span("clickhouse_preflight") as preflight_span:
                try:
                    if not self._clickhouse.ping():
                        raise ClickHousePreflightError("ClickHouse SELECT 1 failed")
                    available_tables = self._clickhouse.list_tables()
                except (ClickHouseNotConfiguredError, ClickHousePreflightError):
                    raise
                except Exception as exc:
                    raise ClickHousePreflightError(
                        "ClickHouse preflight failed"
                    ) from exc
                preflight_span.update(
                    output={"available_table_count": len(available_tables)}
                )

            result = ProcessFeatureResult(
                run_id=run_id,
                status="profiled",
                feature=files.feature,
                rows_loaded=0,
                insights=[],
                langfuse_trace_id=root_span.trace_id,
            )
            with self._tracer.span("persist_profiled_run") as persist_span:
                try:
                    self._run_store.save_profiled_run(
                        result,
                        event_profile=event_profile,
                        spec_sha256=hashlib.sha256(
                            files.spec.encode("utf-8")
                        ).hexdigest(),
                        available_tables=available_tables,
                    )
                except RunStoreError:
                    raise
                except Exception as exc:
                    raise FeaturePipelineError(
                        "Could not persist the profiled pipeline run"
                    ) from exc
                persist_span.update(output={"status": "stored"})

            if self._full_workflow is not None:
                result = self._full_workflow.run(
                    run_id=run_id,
                    trace_id=root_span.trace_id,
                    feature=files.feature,
                    spec=files.spec,
                    profile=event_profile,
                    events_path=files.events_path,
                    available_tables=available_tables,
                )

            root_span.update(
                output={
                    "run_id": result.run_id,
                    "status": result.status,
                    "feature": result.feature,
                    "event_count": event_profile.event_count,
                }
            )
            return result

    def get_run_summary(self, run_id: str) -> RunSummary:
        try:
            return self._run_store.get_run_summary(run_id)
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError("Could not read the pipeline run") from exc

    def get_schema(self, run_id: str) -> SchemaArtifact:
        try:
            return SchemaArtifact.model_validate(
                self._run_store.get_artifact(run_id, "schema")
            )
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError("Could not read the schema artifact") from exc

    def get_context_diff(self, run_id: str) -> ContextDiff:
        try:
            return ContextDiff.model_validate(
                self._run_store.get_artifact(run_id, "context_diff")
            )
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError(
                "Could not read the context-diff artifact"
            ) from exc

    def get_current_context(self) -> ContextDocument:
        """Return the newest accumulated context, empty before the first write."""

        try:
            document = self._run_store.get_latest_context()
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError(
                "Could not read the accumulated semantic context"
            ) from exc
        if document is None:
            return ContextDocument(version=1)
        return document

    def get_context_version(self, version: int) -> ContextDocument:
        """Return one historical context snapshot by version number."""

        try:
            document = self._run_store.get_context_version(version)
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError(
                "Could not read the requested context version"
            ) from exc
        if document is None:
            raise ArtifactNotFoundError(f"Context version not found: {version}")
        return document

    def get_insights(self, run_id: str) -> list[InsightSummary]:
        return self.get_run_summary(run_id).insights

    def get_run_report(self, run_id: str) -> RunReport:
        try:
            return RunReport(
                summary=self._run_store.get_run_summary(run_id),
                artifacts=self._run_store.get_artifacts(run_id),
            )
        except RunStoreError:
            raise
        except Exception as exc:
            raise FeaturePipelineError("Could not read the complete run report") from exc

    def flush_traces(self) -> None:
        self._tracer.flush()


def build_feature_pipeline_service(
    config: Settings,
    *,
    clickhouse: ClickHouseRepository | None = None,
    run_store: RunStore | None = None,
    tracer: Tracer | None = None,
) -> FeaturePipelineService:
    repository = clickhouse or ClickHouseRepository(config)
    durable_store = run_store or ClickHouseRunStore(
        repository,
        database=config.CLICKHOUSE_DATABASE,
    )
    secret_key = (
        config.LANGFUSE_SECRET_KEY.get_secret_value()
        if config.LANGFUSE_SECRET_KEY is not None
        else None
    )
    pipeline_tracer = tracer or create_tracer(
        enabled=config.LANGFUSE_TRACING_ENABLED,
        public_key=config.LANGFUSE_PUBLIC_KEY,
        secret_key=secret_key,
        base_url=(
            str(config.LANGFUSE_BASE_URL).rstrip("/")
            if config.LANGFUSE_BASE_URL is not None
            else None
        ),
    )
    full_workflow: FullFeatureWorkflow | None = None
    if config.FIREWORKS_API_KEY is not None and isinstance(
        durable_store, ClickHouseRunStore
    ):
        full_workflow = FullFeatureWorkflow(
            database=config.CLICKHOUSE_DATABASE,
            clickhouse=repository,
            run_store=durable_store,
            agents=FireworksAgentClient(
                api_key=config.FIREWORKS_API_KEY.get_secret_value(),
                model=config.FIREWORKS_MODEL,
                base_url=str(config.FIREWORKS_BASE_URL),
                timeout=config.FIREWORKS_TIMEOUT,
            ),
            tracer=pipeline_tracer,
        )
    return FeaturePipelineService(
        config=config,
        clickhouse=repository,
        run_store=durable_store,
        tracer=pipeline_tracer,
        full_workflow=full_workflow,
    )


@lru_cache
def get_feature_pipeline_service() -> FeaturePipelineService:
    return build_feature_pipeline_service(settings)


def process_feature_pipeline(
    feature_folder: str,
    *,
    service: FeaturePipeline | None = None,
) -> ProcessFeatureResult:
    """Run the same feature use case regardless of the calling transport."""

    pipeline = service or get_feature_pipeline_service()
    return pipeline.process_feature(feature_folder)


__all__ = [
    "ClickHousePreflightError",
    "FeaturePipeline",
    "FeaturePipelineError",
    "FeaturePipelineService",
    "build_feature_pipeline_service",
    "get_feature_pipeline_service",
    "process_feature_pipeline",
]
