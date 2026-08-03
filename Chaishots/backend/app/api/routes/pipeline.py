from pathlib import Path
from typing import NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.repositories.clickhouse import ClickHouseNotConfiguredError
from app.repositories.run_store import (
    ArtifactNotFoundError,
    RunNotFoundError,
    RunStoreError,
)
from app.schemas.features import (
    ContextDiff,
    ContextDocument,
    FeatureUploadResult,
    InsightSummary,
    ProcessFeatureRequest,
    ProcessFeatureResult,
    RunReport,
    RunSummary,
    SchemaArtifact,
)
from app.services.feature_pipeline import (
    FeaturePipeline,
    FeaturePipelineError,
    get_feature_pipeline_service,
    process_feature_pipeline,
)
from app.tools.event_profiler import EventProfilerError
from app.tools.feature_source import (
    FeatureFileError,
    FeatureNotFoundError,
    FeatureRootError,
    FeatureSourceError,
    InvalidFeatureKeyError,
)
from app.tools.feature_upload import (
    FeatureUploadError,
    FeatureUploadStorageError,
    UploadedFileTooLargeError,
    store_feature_upload,
)

router = APIRouter(tags=["pipeline"])


class FeatureUploadStore:
    """Injectable adapter that keeps multipart handling out of the pipeline."""

    def __init__(
        self,
        features_root: Path = settings.FEATURE_ROOT,
        *,
        max_spec_bytes: int = settings.FEATURE_MAX_SPEC_BYTES,
        max_event_bytes: int = settings.FEATURE_MAX_EVENT_FILE_BYTES,
    ) -> None:
        self._features_root = features_root
        self._max_spec_bytes = max_spec_bytes
        self._max_event_bytes = max_event_bytes

    def store(
        self,
        feature_folder: str,
        *,
        spec: UploadFile,
        events: UploadFile,
    ) -> None:
        store_feature_upload(
            self._features_root,
            feature_folder,
            spec_stream=spec.file,
            events_stream=events.file,
            max_spec_bytes=self._max_spec_bytes,
            max_event_bytes=self._max_event_bytes,
        )


def get_feature_upload_store() -> FeatureUploadStore:
    return FeatureUploadStore()


def _pipeline_error(exc: Exception) -> NoReturn:
    if isinstance(exc, UploadedFileTooLargeError):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        )
    if isinstance(exc, (FeatureNotFoundError, RunNotFoundError, ArtifactNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (InvalidFeatureKeyError, FeatureFileError, EventProfilerError)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    if isinstance(exc, (FeatureRootError, ClickHouseNotConfiguredError)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if isinstance(exc, FeatureUploadStorageError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    if isinstance(exc, (FeaturePipelineError, RunStoreError)):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, FeatureSourceError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    if isinstance(exc, FeatureUploadError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    raise exc


@router.post(
    "/features/upload",
    response_model=FeatureUploadResult,
    status_code=status.HTTP_201_CREATED,
)
def upload_feature(
    feature_folder: str = Form(min_length=1, max_length=128),
    spec: UploadFile = File(description="Feature specification; stored as spec.md"),
    events: UploadFile = File(description="Event data; stored as events.ndjson"),
    upload_store: FeatureUploadStore = Depends(get_feature_upload_store),
) -> FeatureUploadResult:
    """Store a feature folder without starting the processing pipeline."""

    try:
        upload_store.store(feature_folder, spec=spec, events=events)
        return FeatureUploadResult(feature_folder=feature_folder)
    except Exception as exc:
        _pipeline_error(exc)


@router.post("/features/process", response_model=ProcessFeatureResult)
def process_feature(
    request: ProcessFeatureRequest,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> ProcessFeatureResult:
    """Profile a new feature and begin its shared processing pipeline."""

    try:
        return process_feature_pipeline(request.feature_folder, service=service)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run_summary(
    run_id: str,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> RunSummary:
    try:
        return service.get_run_summary(run_id)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/runs/{run_id}/schema", response_model=SchemaArtifact)
def get_schema(
    run_id: str,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> SchemaArtifact:
    try:
        return service.get_schema(run_id)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/runs/{run_id}/context-diff", response_model=ContextDiff)
def get_context_diff(
    run_id: str,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> ContextDiff:
    try:
        return service.get_context_diff(run_id)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/context", response_model=ContextDocument)
def get_current_context(
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> ContextDocument:
    """Return the latest accumulated semantic context across all runs."""

    try:
        return service.get_current_context()
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/context/{version}", response_model=ContextDocument)
def get_context_version(
    version: int,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> ContextDocument:
    """Return one historical context snapshot so versions can be compared."""

    try:
        return service.get_context_version(version)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/runs/{run_id}/insights", response_model=list[InsightSummary])
def get_insights(
    run_id: str,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> list[InsightSummary]:
    try:
        return service.get_insights(run_id)
    except Exception as exc:
        _pipeline_error(exc)


@router.get("/runs/{run_id}/report", response_model=RunReport)
def get_run_report(
    run_id: str,
    service: FeaturePipeline = Depends(get_feature_pipeline_service),
) -> RunReport:
    """Return the persisted end-to-end output used by the run dashboard."""

    try:
        return service.get_run_report(run_id)
    except Exception as exc:
        _pipeline_error(exc)
